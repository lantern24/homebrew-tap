cask "peer" do
  version "0.1.3"
  sha256 "d780ca64953862ba30a95672e6bc83c1871d0609753bb9b5c8f7d396e4c5064c"

  url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-macOS-arm64.app.zip"
  name "Peer"
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"

  depends_on arch: :arm64
  depends_on formula: "git"
  depends_on macos: :ventura

  app "Peer.app"
end
