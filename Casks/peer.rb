cask "peer" do
  version "0.2.1"
  sha256 "c6b17f5161a01f901bf4c375a31da3b1d8806c568ffc095f43bd7087f0b13399"

  url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-macOS-arm64.app.zip"
  name "Peer"
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"

  depends_on arch: :arm64
  depends_on formula: "git"
  depends_on macos: :ventura

  app "Peer.app"
end
