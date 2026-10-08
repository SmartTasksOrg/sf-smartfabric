# Minimal GCP deploy of a single SmartFabric node on a free-tier e2-micro.
# This provisions infrastructure only; it deploys the node service (a real HTTP
# service), not a stub. Review firewall scope before using beyond a demo.
terraform {
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.0" }
  }
}
provider "google" {
  project = var.project
  region  = var.region
  zone    = var.zone
}
variable "project" { type = string }
variable "region"  { type = string, default = "us-west1" }
variable "zone"    { type = string, default = "us-west1-a" }

resource "google_compute_instance" "fabric_node" {
  name         = "smartfabric-node"
  machine_type = "e2-micro" # free tier eligible
  zone         = var.zone

  boot_disk {
    initialize_params { image = "debian-cloud/debian-12" }
  }
  network_interface {
    network = "default"
    access_config {} # ephemeral public IP
  }
  metadata = {
    user-data = file("${path.module}/cloud-init.yaml")
  }
  tags = ["sf-smartfabric"]
}

resource "google_compute_firewall" "fabric" {
  name    = "allow-smartfabric"
  network = "default"
  allow { protocol = "tcp", ports = ["8770"] }
  # NOTE: 0.0.0.0/0 is for demo reachability. Restrict this in production.
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["sf-smartfabric"]
}

output "node_ip" {
  value = google_compute_instance.fabric_node.network_interface[0].access_config[0].nat_ip
}
