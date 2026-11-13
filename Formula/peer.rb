class Peer < Formula
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"
  version "0.6.0"
  license "Apache-2.0"

  on_intel do
    url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-Linux-x86_64.AppImage"
    sha256 "a95bf026c942658e1aed401a139de435113e3f74c671cf18629248bea1210a23"
  end

  on_arm do
    url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-Linux-arm64.AppImage"
    sha256 "23bd7223a18a82aad7c321895ac7a901da0d34a7dfe62c06dd36e872d117eddc"
  end

  depends_on :linux
  depends_on "git"

  def install
    appimage = File.basename(stable.url)
    chmod 0755, appimage
    system "./#{appimage}", "--appimage-extract"
    libexec.install Pathname("squashfs-root").children
    (bin/"peer").write_env_script libexec/"AppRun", {}
  end
end
