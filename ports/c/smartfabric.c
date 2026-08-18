#define _POSIX_C_SOURCE 200809L
/* SmartFabric — C port of the IAIso Fabric Protocol (IFP) core.
 * Independent reimplementation from spec/vectors. Reproduces spec/vectors/*.json
 * exactly (1e-9 numeric, byte-exact envelope). C11, no external libraries
 * (embeds its own SHA-256 and a minimal JSON parser).
 *
 *   cd ports/c && cc -O2 -std=c11 smartfabric.c -o smartfabric -lm && \
 *   ./smartfabric ../../spec/vectors
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <math.h>

static const double TOL = 1e-9;

/* ---------------- JSON value (arena-allocated) ---------------- */
typedef enum { J_NUL, J_BOOL, J_NUM, J_STR, J_ARR, J_OBJ } JT;
typedef struct JV JV;
typedef struct { char *k; JV *v; } JKV;
struct JV {
    JT t;
    int b;
    double n;
    char *s;
    JV **items; int nitems;          /* array */
    JKV *pairs; int npairs;          /* object (kept sorted by key) */
};

static JV *jnew(JT t){ JV *v=calloc(1,sizeof(JV)); v->t=t; return v; }

/* ---------------- parser ---------------- */
typedef struct { const char *s; size_t i; } P;
static void pws(P*p){ while(p->s[p->i]==' '||p->s[p->i]=='\n'||p->s[p->i]=='\t'||p->s[p->i]=='\r') p->i++; }
static JV *pval(P*p);
static char *pstr_raw(P*p){
    p->i++; /* opening quote */
    size_t cap=16,len=0; char *out=malloc(cap);
    while(p->s[p->i]!='"'){
        char c=p->s[p->i++];
        if(c=='\\'){
            char e=p->s[p->i++];
            switch(e){
                case 'n': c='\n'; break; case 't': c='\t'; break; case 'r': c='\r'; break;
                case '"': c='"'; break; case '\\': c='\\'; break; case '/': c='/'; break;
                case 'u': { char hex[5]; memcpy(hex,p->s+p->i,4); hex[4]=0; p->i+=4;
                            long cp=strtol(hex,NULL,16); c=(char)(cp<0x80?cp:'?'); break; }
                default: c=e;
            }
        }
        if(len+1>=cap){ cap*=2; out=realloc(out,cap); }
        out[len++]=c;
    }
    p->i++; out[len]=0; return out;
}
static JV *pobj(P*p){
    JV *v=jnew(J_OBJ); p->i++; pws(p);
    if(p->s[p->i]=='}'){ p->i++; return v; }
    int cap=8; v->pairs=malloc(cap*sizeof(JKV)); v->npairs=0;
    while(1){
        pws(p); char *k=pstr_raw(p); pws(p); p->i++; /* : */
        JV *val=pval(p);
        if(v->npairs>=cap){ cap*=2; v->pairs=realloc(v->pairs,cap*sizeof(JKV)); }
        v->pairs[v->npairs].k=k; v->pairs[v->npairs].v=val; v->npairs++;
        pws(p);
        if(p->s[p->i]==','){ p->i++; continue; }
        p->i++; break;
    }
    /* sort pairs by key (insertion sort; objects are small) */
    for(int a=1;a<v->npairs;a++){ JKV tmp=v->pairs[a]; int b=a-1;
        while(b>=0 && strcmp(v->pairs[b].k,tmp.k)>0){ v->pairs[b+1]=v->pairs[b]; b--; }
        v->pairs[b+1]=tmp; }
    return v;
}
static JV *parr(P*p){
    JV *v=jnew(J_ARR); p->i++; pws(p);
    if(p->s[p->i]==']'){ p->i++; return v; }
    int cap=8; v->items=malloc(cap*sizeof(JV*)); v->nitems=0;
    while(1){
        JV *e=pval(p);
        if(v->nitems>=cap){ cap*=2; v->items=realloc(v->items,cap*sizeof(JV*)); }
        v->items[v->nitems++]=e; pws(p);
        if(p->s[p->i]==','){ p->i++; continue; }
        p->i++; break;
    }
    return v;
}
static JV *pval(P*p){
    pws(p); char c=p->s[p->i];
    if(c=='{') return pobj(p);
    if(c=='[') return parr(p);
    if(c=='"'){ JV *v=jnew(J_STR); v->s=pstr_raw(p); return v; }
    if(c=='t'){ p->i+=4; JV *v=jnew(J_BOOL); v->b=1; return v; }
    if(c=='f'){ p->i+=5; JV *v=jnew(J_BOOL); v->b=0; return v; }
    if(c=='n'){ p->i+=4; return jnew(J_NUL); }
    { size_t st=p->i; while(strchr("-+.eE0123456789",p->s[p->i])) p->i++;
      char *buf=strndup(p->s+st,p->i-st); JV *v=jnew(J_NUM); v->n=atof(buf); free(buf); return v; }
}

static JV *jget(JV *o, const char *k){
    if(!o||o->t!=J_OBJ) return NULL;
    for(int i=0;i<o->npairs;i++) if(strcmp(o->pairs[i].k,k)==0) return o->pairs[i].v;
    return NULL;
}
static double jnumk(JV *o,const char*k){ JV *v=jget(o,k); return v?v->n:0.0; }

/* ---------------- pressure ---------------- */
typedef struct {
    double escalation, release, diss_step, diss_sec, token_c, tool_c, depth_c, warning;
    int post_release_lock;
} Config;
static Config default_config(void){
    Config c={0.85,0.95,0.02,0.0,0.015,0.08,0.05,0.70,1}; return c;
}
static const char *zone(Config *c,double p){
    if(p>=c->release) return "release";
    if(p>=c->escalation) return "escalation";
    if(p>=c->warning) return "warning";
    return "nominal";
}
static double clampd(double v){ return v<0?0:(v>1?1:v); }
typedef struct { Config c; double p; int locked; } Engine;
static void estep(Engine *e,double tokens,double tools,double depth,double seconds,
                  double *np,const char **z,int *released,int *lok){
    if(e->locked && e->c.post_release_lock){ *np=e->p; *z=zone(&e->c,e->p); *released=0; *lok=1; return; }
    double intake=(tokens/1000.0)*e->c.token_c + tools*e->c.tool_c + depth*e->c.depth_c;
    double diss=e->c.diss_step + e->c.diss_sec*seconds;
    double v=clampd(e->p+intake-diss);
    if(v>=e->c.release-TOL){ e->p=0; e->locked=e->c.post_release_lock; *np=0; *z="release"; *released=1; *lok=e->locked; return; }
    e->p=v; *np=e->p; *z=zone(&e->c,e->p); *released=0; *lok=0;
}

/* ---------------- canonical JSON ---------------- */
typedef struct { char *buf; size_t len, cap; } SB;
static void sb_init(SB*b){ b->cap=64; b->buf=malloc(b->cap); b->len=0; b->buf[0]=0; }
static void sb_putc(SB*b,char c){ if(b->len+2>b->cap){ b->cap*=2; b->buf=realloc(b->buf,b->cap);} b->buf[b->len++]=c; b->buf[b->len]=0; }
static void sb_puts(SB*b,const char*s){ while(*s) sb_putc(b,*s++); }
static void sb_quote(SB*b,const char*s){
    sb_putc(b,'"');
    for(const unsigned char*p=(const unsigned char*)s;*p;p++){
        unsigned char c=*p;
        if(c=='"'){ sb_puts(b,"\\\""); }
        else if(c=='\\'){ sb_puts(b,"\\\\"); }
        else if(c=='\n'){ sb_puts(b,"\\n"); }
        else if(c=='\r'){ sb_puts(b,"\\r"); }
        else if(c=='\t'){ sb_puts(b,"\\t"); }
        else if(c<0x20){ char t[8]; snprintf(t,sizeof t,"\\u%04x",c); sb_puts(b,t); }
        else sb_putc(b,(char)c);
    }
    sb_putc(b,'"');
}
/* shortest round-trip double: try increasing precision until it round-trips */
static void fmt_num(SB*b,double n){
    if(n==trunc(n) && fabs(n)<1e15){ char t[32]; snprintf(t,sizeof t,"%lld",(long long)n); sb_puts(b,t); return; }
    char t[40];
    for(int prec=1; prec<=17; prec++){
        snprintf(t,sizeof t,"%.*g",prec,n);
        if(atof(t)==n) break;
    }
    sb_puts(b,t);
}
static void canon(SB*b, JV*v){
    switch(v->t){
        case J_NUL: sb_puts(b,"null"); break;
        case J_BOOL: sb_puts(b, v->b?"true":"false"); break;
        case J_STR: sb_quote(b,v->s); break;
        case J_NUM: fmt_num(b,v->n); break;
        case J_ARR: { sb_putc(b,'['); for(int i=0;i<v->nitems;i++){ if(i)sb_putc(b,','); canon(b,v->items[i]); } sb_putc(b,']'); break; }
        case J_OBJ: { sb_putc(b,'{'); int first=1;
            for(int i=0;i<v->npairs;i++){ if(v->pairs[i].v->t==J_NUL) continue;
                if(!first)sb_putc(b,','); first=0; sb_quote(b,v->pairs[i].k); sb_putc(b,':'); canon(b,v->pairs[i].v); }
            sb_putc(b,'}'); break; }
    }
}
static JV *drop_null(JV *o){
    if(!o||o->t!=J_OBJ) return o;
    JV *out=jnew(J_OBJ); out->pairs=malloc(o->npairs*sizeof(JKV)); out->npairs=0;
    for(int i=0;i<o->npairs;i++) if(o->pairs[i].v->t!=J_NUL) out->pairs[out->npairs++]=o->pairs[i];
    return out; /* already sorted (source was sorted) */
}
static void obj_put(JV *o,const char*k,JV*v){
    o->pairs=realloc(o->pairs,(o->npairs+1)*sizeof(JKV));
    o->pairs[o->npairs].k=strdup(k); o->pairs[o->npairs].v=v; o->npairs++;
    for(int a=1;a<o->npairs;a++){ JKV tmp=o->pairs[a]; int b=a-1;
        while(b>=0 && strcmp(o->pairs[b].k,tmp.k)>0){ o->pairs[b+1]=o->pairs[b]; b--; }
        o->pairs[b+1]=tmp; }
}
static JV *normalize_envelope(JV *m){
    JV *out=jnew(J_OBJ); out->pairs=NULL; out->npairs=0;
    obj_put(out,"header", drop_null(jget(m,"header")));
    JV *pol=jget(m,"policy");
    obj_put(out,"policy", pol?drop_null(pol):jnew(J_OBJ));
    const char *opt[]={"auth","body","meta"};
    for(int i=0;i<3;i++){ JV *v=jget(m,opt[i]); if(v && v->t==J_OBJ && v->npairs>0) obj_put(out,opt[i],v); }
    return out;
}

/* ---------------- SHA-256 ---------------- */
static uint32_t rotr(uint32_t x,int n){ return (x>>n)|(x<<(32-n)); }
static void sha256_hex(const unsigned char *data,size_t len,char out[65]){
    uint32_t h[8]={0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19};
    static const uint32_t K[64]={
        0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2};
    size_t ml=len; size_t padded=((len+8)/64+1)*64;
    unsigned char *msg=calloc(padded,1); memcpy(msg,data,len); msg[len]=0x80;
    uint64_t bitlen=(uint64_t)ml*8;
    for(int i=0;i<8;i++) msg[padded-1-i]=(bitlen>>(i*8))&0xff;
    for(size_t off=0;off<padded;off+=64){
        uint32_t w[64];
        for(int i=0;i<16;i++)
            w[i]=(msg[off+i*4]<<24)|(msg[off+i*4+1]<<16)|(msg[off+i*4+2]<<8)|(msg[off+i*4+3]);
        for(int i=16;i<64;i++){
            uint32_t s0=rotr(w[i-15],7)^rotr(w[i-15],18)^(w[i-15]>>3);
            uint32_t s1=rotr(w[i-2],17)^rotr(w[i-2],19)^(w[i-2]>>10);
            w[i]=w[i-16]+s0+w[i-7]+s1;
        }
        uint32_t a=h[0],b=h[1],c=h[2],d=h[3],e=h[4],f=h[5],g=h[6],hh=h[7];
        for(int i=0;i<64;i++){
            uint32_t S1=rotr(e,6)^rotr(e,11)^rotr(e,25);
            uint32_t ch=(e&f)^((~e)&g);
            uint32_t t1=hh+S1+ch+K[i]+w[i];
            uint32_t S0=rotr(a,2)^rotr(a,13)^rotr(a,22);
            uint32_t maj=(a&b)^(a&c)^(b&c);
            uint32_t t2=S0+maj;
            hh=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
        }
        h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=hh;
    }
    free(msg);
    for(int i=0;i<8;i++) snprintf(out+i*8,9,"%08x",h[i]);
}

/* ---------------- runner ---------------- */
static int PASS=0, FAILN=0;
static void report(const char*fam,const char*name,int ok,const char*detail){
    if(ok)PASS++;else FAILN++;
    printf("%s%-9s %-28s %s\n", ok?"OK ":"XX ", fam, name, detail?detail:"");
}
static char *readfile(const char*path){
    FILE*f=fopen(path,"rb"); if(!f){ fprintf(stderr,"cannot open %s\n",path); exit(2); }
    fseek(f,0,SEEK_END); long n=ftell(f); fseek(f,0,SEEK_SET);
    char *buf=malloc(n+1); if(fread(buf,1,n,f)!=(size_t)n){} buf[n]=0; fclose(f); return buf;
}
static int approx(double a,double b){ return fabs(a-b)<=TOL; }
static void apply_config(Config*c, JV*conf){
    JV*v;
    if((v=jget(conf,"escalation_threshold"))) c->escalation=v->n;
    if((v=jget(conf,"release_threshold"))) c->release=v->n;
    if((v=jget(conf,"dissipation_per_step"))) c->diss_step=v->n;
    if((v=jget(conf,"dissipation_per_second"))) c->diss_sec=v->n;
    if((v=jget(conf,"token_coefficient"))) c->token_c=v->n;
    if((v=jget(conf,"tool_coefficient"))) c->tool_c=v->n;
    if((v=jget(conf,"depth_coefficient"))) c->depth_c=v->n;
    if((v=jget(conf,"post_release_lock"))) c->post_release_lock=v->b;
}

int main(int argc,char**argv){
    const char *dir = argc>1?argv[1]:"../../spec/vectors";
    char path[512];

    /* pressure */
    snprintf(path,sizeof path,"%s/pressure.vectors.json",dir);
    { P p={readfile(path),0}; JV*data=pval(&p); JV*cases=jget(data,"cases");
      for(int ci=0;ci<cases->nitems;ci++){ JV*c=cases->items[ci];
        Config cfg=default_config(); JV*conf=jget(c,"config"); if(conf) apply_config(&cfg,conf);
        Engine eng={cfg,0,0}; JV*steps=jget(c,"steps"); JV*exp=jget(c,"expect");
        int ok=1; char detail[32]=""; 
        for(int k=0;k<steps->nitems;k++){ JV*st=steps->items[k];
            double np; const char*z; int rel,lok;
            estep(&eng,jnumk(st,"tokens"),jnumk(st,"tool_calls"),jnumk(st,"depth"),jnumk(st,"seconds"),&np,&z,&rel,&lok);
            JV*e=exp->items[k];
            if(!approx(np,jnumk(e,"p"))){ ok=0; snprintf(detail,sizeof detail,"p@%d",k); break; }
            if(strcmp(z,jget(e,"zone")->s)||rel!=jget(e,"released")->b||lok!=jget(e,"locked")->b){
                ok=0; snprintf(detail,sizeof detail,"field@%d",k); break; }
        }
        report("pressure", jget(c,"name")->s, ok, detail);
      }
    }
    /* fleet */
    snprintf(path,sizeof path,"%s/fleet.vectors.json",dir);
    { P p={readfile(path),0}; JV*data=pval(&p); JV*cases=jget(data,"cases");
      for(int ci=0;ci<cases->nitems;ci++){ JV*c=cases->items[ci];
        JV*et=jget(c,"escalation_threshold"); double esc=et?et->n:0.85;
        JV*nodes=jget(c,"nodes");
        double totalW=0,weighted=0,peakP=-1; const char*peak=NULL;
        for(int i=0;i<nodes->nitems;i++){ JV*nd=nodes->items[i];
            double pr=jnumk(nd,"pressure");
            JV*cc=jget(nd,"centrality"); double ce=cc?(cc->n<0?0:cc->n):1.0;
            totalW+=ce; weighted+=pr*ce;
            if(pr>peakP){ peakP=pr; peak=jget(nd,"node_id")->s; }
        }
        if(totalW==0) totalW=nodes->nitems;
        double pf = nodes->nitems==0?0.0:clampd(weighted/totalW);
        JV*e=jget(c,"expect");
        int ok=approx(pf,jnumk(e,"P_fleet"));
        JV*pn=jget(e,"peak_node");
        if(ok && pn && pn->t==J_STR) ok = peak && strcmp(peak,pn->s)==0;
        report("fleet", jget(c,"name")->s, ok, "");
      }
    }
    /* envelope */
    snprintf(path,sizeof path,"%s/envelope.vectors.json",dir);
    { P p={readfile(path),0}; JV*data=pval(&p); JV*cases=jget(data,"cases");
      for(int ci=0;ci<cases->nitems;ci++){ JV*c=cases->items[ci];
        JV*norm=normalize_envelope(jget(c,"message"));
        SB b; sb_init(&b); canon(&b,norm);
        JV*e=jget(c,"expect");
        int ok = strcmp(b.buf,jget(e,"canonical_json")->s)==0; const char*detail= ok?"":"canonical_json";
        if(ok){ char sha[65]; sha256_hex((unsigned char*)b.buf,b.len,sha);
            char full[80]; snprintf(full,sizeof full,"sha256:%s",sha);
            if(strcmp(full,jget(e,"canonical_sha256")->s)){ ok=0; detail="sha"; } }
        if(ok){ /* framed_hex = varint(len)+canon, hex-encoded */
            SB fb; sb_init(&fb); size_t n=b.len;
            unsigned char vbuf[8]; int vn=0;
            while(1){ unsigned char x=n&0x7f; n>>=7; if(n) vbuf[vn++]=x|0x80; else { vbuf[vn++]=x; break; } }
            char hex[4]; for(int i=0;i<vn;i++){ snprintf(hex,sizeof hex,"%02x",vbuf[i]); sb_puts(&fb,hex); }
            for(size_t i=0;i<b.len;i++){ snprintf(hex,sizeof hex,"%02x",(unsigned char)b.buf[i]); sb_puts(&fb,hex); }
            if(strcmp(fb.buf,jget(e,"framed_hex")->s)){ ok=0; detail="framed"; }
            free(fb.buf);
        }
        report("envelope", jget(c,"name")->s, ok, detail);
        free(b.buf);
      }
    }

    printf("---\npass=%d fail=%d\n", PASS, FAILN);
    return FAILN==0?0:1;
}
