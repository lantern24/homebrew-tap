cask "peer" do
  version "0.1.1"
  sha256 "02430ec7643558848be8a21ddd8bc9055bf6871c0bfa5a308787dd9ca0636239"

  url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-macOS-arm64.app.zip"
  name "Peer"
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"

  depends_on arch: :arm64
  depends_on formula: "git"
  depends_on macos: :ventura

  app "Peer.app"
end
