// SmartFabric — C++ port of the IAIso Fabric Protocol (IFP) core.
// Independent reimplementation from spec/vectors. Reproduces spec/vectors/*.json
// exactly (1e-9 numeric, byte-exact envelope). Single translation unit, only the
// C++17 standard library (embeds its own SHA-256 and JSON parser).
//
//   cd ports/cpp && g++ -O2 -std=c++17 smartfabric.cpp -o smartfabric && \
//   ./smartfabric ../../spec/vectors

#include <charconv>
#include <cstdint>
#include <cmath>
#include <cstdio>
#include <fstream>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

static const double TOL = 1e-9;

// ----------------------------- JSON value ---------------------------------
struct JV;
using JMap = std::map<std::string, JV>;
using JArr = std::vector<JV>;

struct JV {
    enum T { NUL, BOOL, NUM, STR, ARR, OBJ } t = NUL;
    bool b = false; double n = 0; std::string s;
    std::shared_ptr<JArr> arr; std::shared_ptr<JMap> obj;
    bool isnum() const { return t == NUM; }
    double num() const { return n; }
    const std::string& str() const { return s; }
    bool boolean() const { return b; }
    const JV* get(const std::string& k) const {
        if (t != OBJ) return nullptr;
        auto it = obj->find(k); return it == obj->end() ? nullptr : &it->second;
    }
    double numk(const std::string& k) const { auto* v = get(k); return v ? v->n : 0.0; }
};

// ----------------------------- JSON parser --------------------------------
struct JP {
    std::string s; size_t i = 0;
    JP(std::string str) : s(std::move(str)) {}
    void ws() { while (i < s.size() && (s[i]==' '||s[i]=='\n'||s[i]=='\t'||s[i]=='\r')) i++; }
    JV val() {
        ws();
        char c = s[i];
        if (c == '{') return obj();
        if (c == '[') return arr();
        if (c == '"') { JV v; v.t = JV::STR; v.s = str(); return v; }
        if (c == 't') { i += 4; JV v; v.t = JV::BOOL; v.b = true; return v; }
        if (c == 'f') { i += 5; JV v; v.t = JV::BOOL; v.b = false; return v; }
        if (c == 'n') { i += 4; return JV{}; }
        return num();
    }
    JV obj() {
        JV v; v.t = JV::OBJ; v.obj = std::make_shared<JMap>(); i++; ws();
        if (s[i] == '}') { i++; return v; }
        while (true) {
            ws(); std::string k = str(); ws(); i++; // :
            (*v.obj)[k] = val(); ws();
            if (s[i] == ',') { i++; continue; }
            i++; break;
        }
        return v;
    }
    JV arr() {
        JV v; v.t = JV::ARR; v.arr = std::make_shared<JArr>(); i++; ws();
        if (s[i] == ']') { i++; return v; }
        while (true) {
            v.arr->push_back(val()); ws();
            if (s[i] == ',') { i++; continue; }
            i++; break;
        }
        return v;
    }
    std::string str() {
        std::string out; i++; // opening quote
        while (s[i] != '"') {
            char c = s[i++];
            if (c == '\\') {
                char e = s[i++];
                switch (e) {
                    case 'n': out += '\n'; break; case 't': out += '\t'; break;
                    case 'r': out += '\r'; break; case '"': out += '"'; break;
                    case '\\': out += '\\'; break; case '/': out += '/'; break;
                    case 'u': { int cp = std::stoi(s.substr(i,4),nullptr,16); i+=4;
                                if (cp < 0x80) out += (char)cp; else out += '?'; break; }
                    default: out += e;
                }
            } else out += c;
        }
        i++; return out;
    }
    JV num() {
        size_t start = i;
        while (i < s.size() && (isdigit(s[i])||s[i]=='-'||s[i]=='+'||s[i]=='.'||s[i]=='e'||s[i]=='E')) i++;
        JV v; v.t = JV::NUM; v.n = std::stod(s.substr(start, i-start)); return v;
    }
};

// ----------------------------- pressure -----------------------------------
struct Config {
    double escalation=0.85, release=0.95, diss_step=0.02, diss_sec=0.0;
    double token_c=0.015, tool_c=0.08, depth_c=0.05, warning=0.70;
    bool post_release_lock=true;
};
static std::string zone(const Config& c, double p) {
    if (p >= c.release) return "release";
    if (p >= c.escalation) return "escalation";
    if (p >= c.warning) return "warning";
    return "nominal";
}
static double clampd(double v){ return std::max(0.0, std::min(1.0, v)); }
struct Engine {
    Config c; double p=0.0; bool locked=false;
    Engine(Config cc):c(cc){}
    // out params: np, z, released, lok
    void step(double tokens,double tools,double depth,double seconds,
              double& np,std::string& z,bool& released,bool& lok){
        if (locked && c.post_release_lock){ np=p; z=zone(c,p); released=false; lok=true; return; }
        double intake=(tokens/1000.0)*c.token_c + tools*c.tool_c + depth*c.depth_c;
        double diss=c.diss_step + c.diss_sec*seconds;
        double v=clampd(p+intake-diss);
        if (v >= c.release - TOL){ p=0.0; locked=c.post_release_lock; np=0.0; z="release"; released=true; lok=locked; return; }
        p=v; np=p; z=zone(c,p); released=false; lok=false;
    }
};

// ----------------------------- canonical JSON -----------------------------
static std::string quote(const std::string& s){
    std::string o="\"";
    for(char c: s){
        switch(c){
            case '"': o+="\\\""; break; case '\\': o+="\\\\"; break;
            case '\n': o+="\\n"; break; case '\r': o+="\\r"; break; case '\t': o+="\\t"; break;
            default:
                if((unsigned char)c < 0x20){ char buf[8]; snprintf(buf,sizeof buf,"\\u%04x",c); o+=buf; }
                else o+=c;
        }
    }
    o+="\""; return o;
}
static std::string canon(const JV& v){
    switch(v.t){
        case JV::NUL: return "null";
        case JV::BOOL: return v.b?"true":"false";
        case JV::STR: return quote(v.s);
        case JV::NUM: {
            if (v.n == std::trunc(v.n) && std::fabs(v.n) < 1e15){
                char buf[32]; snprintf(buf,sizeof buf,"%lld",(long long)v.n); return buf;
            }
            // shortest round-trip representation (matches Python repr / JS)
            char buf[32];
            auto r = std::to_chars(buf, buf + sizeof buf, v.n);
            return std::string(buf, r.ptr);
        }
        case JV::ARR: {
            std::string o="["; bool first=true;
            for(auto& e:*v.arr){ if(!first)o+=","; first=false; o+=canon(e); }
            return o+"]";
        }
        case JV::OBJ: {
            std::string o="{"; bool first=true;
            for(auto& kv:*v.obj){ // std::map is already key-sorted
                if(kv.second.t==JV::NUL) continue;
                if(!first)o+=","; first=false;
                o+=quote(kv.first)+":"+canon(kv.second);
            }
            return o+"}";
        }
    }
    return "null";
}
static JV drop_null(const JV& v){
    if (v.t != JV::OBJ) return v;
    JV out; out.t=JV::OBJ; out.obj=std::make_shared<JMap>();
    for(auto& kv:*v.obj) if(kv.second.t!=JV::NUL) (*out.obj)[kv.first]=kv.second;
    return out;
}
static JV normalize_envelope(const JV& m){
    JV out; out.t=JV::OBJ; out.obj=std::make_shared<JMap>();
    (*out.obj)["header"] = drop_null(*m.get("header"));
    auto* pol = m.get("policy");
    (*out.obj)["policy"] = pol ? drop_null(*pol) : [](){ JV e; e.t=JV::OBJ; e.obj=std::make_shared<JMap>(); return e; }();
    for (const char* k : {"auth","body","meta"}){
        auto* v = m.get(k);
        if (v && v->t==JV::OBJ && !v->obj->empty()) (*out.obj)[k]=*v;
    }
    return out;
}

// ----------------------------- SHA-256 ------------------------------------
struct SHA256 {
    uint32_t h[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    static uint32_t rr(uint32_t x,int n){ return (x>>n)|(x<<(32-n)); }
    std::string hex(const std::string& data){
        static const uint32_t K[64]={
            0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
            0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
            0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
            0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
            0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
            0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
            0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
            0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
        std::string msg=data; uint64_t bitlen=(uint64_t)data.size()*8;
        msg+=(char)0x80; while (msg.size()%64!=56) msg+=(char)0;
        for(int i=7;i>=0;i--) msg+=(char)((bitlen>>(i*8))&0xff);
        for(size_t off=0; off<msg.size(); off+=64){
            uint32_t w[64];
            for(int i=0;i<16;i++)
                w[i]=((uint8_t)msg[off+i*4]<<24)|((uint8_t)msg[off+i*4+1]<<16)|((uint8_t)msg[off+i*4+2]<<8)|((uint8_t)msg[off+i*4+3]);
            for(int i=16;i<64;i++){
                uint32_t s0=rr(w[i-15],7)^rr(w[i-15],18)^(w[i-15]>>3);
                uint32_t s1=rr(w[i-2],17)^rr(w[i-2],19)^(w[i-2]>>10);
                w[i]=w[i-16]+s0+w[i-7]+s1;
            }
            uint32_t a=h[0],b=h[1],c=h[2],d=h[3],e=h[4],f=h[5],g=h[6],hh=h[7];
            for(int i=0;i<64;i++){
                uint32_t S1=rr(e,6)^rr(e,11)^rr(e,25);
                uint32_t ch=(e&f)^((~e)&g);
                uint32_t t1=hh+S1+ch+K[i]+w[i];
                uint32_t S0=rr(a,2)^rr(a,13)^rr(a,22);
                uint32_t maj=(a&b)^(a&c)^(b&c);
                uint32_t t2=S0+maj;
                hh=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
            }
            h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=hh;
        }
        char out[65];
        for(int i=0;i<8;i++) snprintf(out+i*8,9,"%08x",h[i]);
        return std::string(out,64);
    }
};
static std::string bytes_to_hex(const std::string& b){
    std::string o; char buf[4];
    for(unsigned char c: b){ snprintf(buf,sizeof buf,"%02x",c); o+=buf; }
    return o;
}
static std::string varint(size_t n){
    std::string o;
    while(true){ unsigned char x=n&0x7f; n>>=7; if(n) o+=(char)(x|0x80); else { o+=(char)x; break; } }
    return o;
}

// ----------------------------- runner -------------------------------------
static int PASS=0, FAILN=0;
static void report(const char* fam,const std::string& name,bool ok,const std::string& detail){
    if(ok)PASS++;else FAILN++;
    printf("%s%-9s %-28s %s\n", ok?"OK ":"XX ", fam, name.c_str(), detail.c_str());
}
static std::string readfile(const std::string& p){
    std::ifstream f(p); std::stringstream ss; ss<<f.rdbuf(); return ss.str();
}
static bool approx(double a,double b){ return std::fabs(a-b)<=TOL; }

static void apply_config(Config& c, const JV& conf){
    if(auto*v=conf.get("escalation_threshold")) c.escalation=v->n;
    if(auto*v=conf.get("release_threshold")) c.release=v->n;
    if(auto*v=conf.get("dissipation_per_step")) c.diss_step=v->n;
    if(auto*v=conf.get("dissipation_per_second")) c.diss_sec=v->n;
    if(auto*v=conf.get("token_coefficient")) c.token_c=v->n;
    if(auto*v=conf.get("tool_coefficient")) c.tool_c=v->n;
    if(auto*v=conf.get("depth_coefficient")) c.depth_c=v->n;
    if(auto*v=conf.get("post_release_lock")) c.post_release_lock=v->b;
}

int main(int argc,char**argv){
    std::string dir = argc>1 ? argv[1] : "../../spec/vectors";

    { // pressure
        JP jp(readfile(dir+"/pressure.vectors.json")); JV data=jp.val();
        for(auto& c : *data.get("cases")->arr){
            Config cfg; if(auto*conf=c.get("config")) apply_config(cfg,*conf);
            Engine eng(cfg);
            auto& steps=*c.get("steps")->arr; auto& exp=*c.get("expect")->arr;
            bool ok=true; std::string detail;
            for(size_t k=0;k<steps.size();k++){
                double np; std::string z; bool rel,lok;
                eng.step(steps[k].numk("tokens"),steps[k].numk("tool_calls"),
                         steps[k].numk("depth"),steps[k].numk("seconds"),np,z,rel,lok);
                auto& e=exp[k];
                if(!approx(np,e.numk("p"))){ok=false;detail="p@"+std::to_string(k);break;}
                if(z!=e.get("zone")->str()||rel!=e.get("released")->b||lok!=e.get("locked")->b){
                    ok=false;detail="field@"+std::to_string(k);break;}
            }
            report("pressure", c.get("name")->str(), ok, detail);
        }
    }
    { // fleet
        JP jp(readfile(dir+"/fleet.vectors.json")); JV data=jp.val();
        for(auto& c : *data.get("cases")->arr){
            double esc = c.get("escalation_threshold")? c.get("escalation_threshold")->n : 0.85;
            auto& nodes=*c.get("nodes")->arr;
            double totalW=0,weighted=0,peakP=-1; std::string peak;
            for(auto& n: nodes){
                double pr=n.numk("pressure");
                double ce = n.get("centrality")? std::max(n.get("centrality")->n,0.0) : 1.0;
                totalW+=ce; weighted+=pr*ce;
                if(pr>peakP){peakP=pr; peak=n.get("node_id")->str();}
            }
            if(totalW==0) totalW=nodes.size();
            double pf = nodes.empty()?0.0:clampd(weighted/totalW);
            auto& e=*c.get("expect");
            bool ok=approx(pf,e.numk("P_fleet"));
            if(ok){ auto* pn=e.get("peak_node"); if(pn && pn->t==JV::STR) ok=(peak==pn->str()); }
            report("fleet", c.get("name")->str(), ok, "");
        }
    }
    { // envelope
        JP jp(readfile(dir+"/envelope.vectors.json")); JV data=jp.val();
        for(auto& c : *data.get("cases")->arr){
            std::string cj=canon(normalize_envelope(*c.get("message")));
            auto& e=*c.get("expect");
            bool ok = cj==e.get("canonical_json")->str(); std::string detail= ok?"":"canonical_json";
            if(ok){
                SHA256 sh; std::string sha="sha256:"+sh.hex(cj);
                if(sha!=e.get("canonical_sha256")->str()){ok=false;detail="sha";}
            }
            if(ok){
                std::string framed=varint(cj.size())+cj;
                if(bytes_to_hex(framed)!=e.get("framed_hex")->str()){ok=false;detail="framed";}
            }
            report("envelope", c.get("name")->str(), ok, detail);
        }
    }

    printf("---\npass=%d fail=%d\n", PASS, FAILN);
    return FAILN==0?0:1;
}
