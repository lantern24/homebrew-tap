cask "peer" do
  version "0.2.0"
  sha256 "cdfd41e2fc24dbaa8cf724a7c2b71475f84a968a18b54ccdd72892b41a98214b"

  url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-macOS-arm64.app.zip"
  name "Peer"
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"

  depends_on arch: :arm64
  depends_on formula: "git"
  depends_on macos: :ventura

  app "Peer.app"
end
