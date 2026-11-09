cask "peer" do
  version "0.5.0"
  sha256 "2f7a1bf71f190e815612d490b363a784ca79a332a566d8cf6582e1bb284e3f53"

  url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-macOS-arm64.app.zip"
  name "Peer"
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"

  depends_on arch: :arm64
  depends_on formula: "git"
  depends_on macos: :ventura

  app "Peer.app"
end
