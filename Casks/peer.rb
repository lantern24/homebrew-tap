cask "peer" do
  version "0.3.1"
  sha256 "e06a8533fe2dd4a234e9b169c99335b8deb24d432e58c8b4dd510c8bdaed627f"

  url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-macOS-arm64.app.zip"
  name "Peer"
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"

  depends_on arch: :arm64
  depends_on formula: "git"
  depends_on macos: :ventura

  app "Peer.app"
end
