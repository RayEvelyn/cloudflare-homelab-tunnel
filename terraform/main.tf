terraform {
  backend "local" {}
  required_version = ">= 1.6.0, < 2.0.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "5.26.0"
    }
  }
}
# CLOUDFlARE_API_TOKEN is read by the provider; never put it in variables.
provider "cloudflare" {}
variable "zone_id" {
  type = string
}
variable "hostname" {
  type = string
}
variable "tunnel_id" {
  type = string
  validation {
    condition     = can(regex("^[a-f0-9-]{36}$", var.tunnel_id))
    error_message = "Use the UUID returned by the named tunnel create helper."
  }
}
resource "cloudflare_dns_record" "website" {
  zone_id = var.zone_id
  name    = var.hostname
  type    = "CNAME"
  content = "${var.tunnel_id}.cfargotunnel.com"
  ttl     = 1
  proxied = true
}
output "website_url" {
  value = "https://${var.hostname}"
}
