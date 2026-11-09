class Peer < Formula
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"
  version "0.5.0"
  license "Apache-2.0"

  on_intel do
    url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-Linux-x86_64.AppImage"
    sha256 "6a4570da34c1b9989920993870b2b2870c324362820950040af8cff65f28248a"
  end

  on_arm do
    url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-Linux-arm64.AppImage"
    sha256 "e763f2c88d1b8fc99c23db7872d1001552234b5bba5b3b6f278239b1cddf9ed7"
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
