class Peer < Formula
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"
  version "0.2.1"
  license "Apache-2.0"

  on_intel do
    url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-Linux-x86_64.AppImage"
    sha256 "92ffabd5c6e7b6640eea2ed0797d50701cb10fffac7a9c67c6a3469f7d8b14f9"
  end

  on_arm do
    url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-Linux-arm64.AppImage"
    sha256 "030545b8adcb04262abf85463c137c00f18195719b01e6a34d8a742c0734ba9c"
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
