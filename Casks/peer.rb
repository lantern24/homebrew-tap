cask "peer" do
  version "0.6.1"
  sha256 "62c7920365cce7298b0d7d2be7c89a95c594fe5f3eb98121f3f327cca2768ae6"

  url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-macOS-arm64.app.zip"
  name "Peer"
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"

  depends_on arch: :arm64
  depends_on formula: "git"
  depends_on macos: :ventura

  app "Peer.app"
end
