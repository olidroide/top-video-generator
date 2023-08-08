variable "TAG" {
    default = "latest"
}

group "default" {
    targets = ["top-video-generator-dev"]
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
    platforms = [
    "linux/amd64",
    ]
}