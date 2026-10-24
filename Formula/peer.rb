class Peer < Formula
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"
  version "0.3.0"
  license "Apache-2.0"

  on_intel do
    url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-Linux-x86_64.AppImage"
    sha256 "2c368d7cfda624b476a54cc6b3a093e388e78b5718c92af1cf1ca8999fdab8d5"
  end

  on_arm do
    url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-Linux-arm64.AppImage"
    sha256 "38331aeebc281f9a9c45897c75b6a827131e068ce1d7bf895877eb9b8f32c625"
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
