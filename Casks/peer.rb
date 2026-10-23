cask "peer" do
  version "0.3.0"
  sha256 "16e593941be07a3b8542a1cc68027f3e182ca9ac083a085be9d07192250859ca"

  url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-macOS-arm64.app.zip"
  name "Peer"
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"

  depends_on arch: :arm64
  depends_on formula: "git"
  depends_on macos: :ventura

  app "Peer.app"
end
