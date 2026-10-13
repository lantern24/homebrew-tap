cask "peer" do
  version "0.1.0"
  sha256 "499f178135a991c74bccec60654ae9924b6dd038b30d241f9eab0e9736d08df2"

  url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-macOS-arm64.app.zip"
  name "Peer"
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"

  depends_on arch: :arm64
  depends_on formula: "git"
  depends_on macos: :ventura

  app "Peer.app"
end
