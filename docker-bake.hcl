variable "TAG" {
    default = "latest"
}

variable "REGISTRY_IMAGE" {
    default = "ghcr.io/olidroide/top-video-generator"
}

group "default" {
    targets = ["top-video-generator-local"]
}

target "top-video-generator-dev" {
    context = "."
    dockerfile = "Dockerfile"
    tags = ["top-video-generator:${TAG}"]
}

target "top-video-generator-local" {
  inherits = ["top-video-generator-dev"]
  output = ["type=docker"]
}

target "top-video-generator-release" {
    inherits = ["top-video-generator-dev"]
    tags = ["${REGISTRY_IMAGE}:${TAG}"]
    platforms = [
    "linux/amd64",
    "linux/arm64",
    ]
    cache-from = ["type=gha,scope=top-video-generator-release"]
    cache-to = ["type=gha,scope=top-video-generator-release,mode=max"]
}
