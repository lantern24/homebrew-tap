cask "peer" do
  version "0.6.0"
  sha256 "87ebcd4791f55e621808de549e00f13b945862b4140e48594b7a8d8b4e9b3d2d"

  url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-macOS-arm64.app.zip"
  name "Peer"
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"

  depends_on arch: :arm64
  depends_on formula: "git"
  depends_on macos: :ventura

  app "Peer.app"
end
