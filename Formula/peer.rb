class Peer < Formula
  desc "Local repository viewer and code review workspace"
  homepage "https://github.com/lantern24/peer"
  version "0.4.0"
  license "Apache-2.0"

  on_intel do
    url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-Linux-x86_64.AppImage"
    sha256 "e562d0b3ff81583142413464eb94fe45e96962a13c2197586ebcac26df02e596"
  end

  on_arm do
    url "https://github.com/lantern24/peer/releases/download/v#{version}/Peer-Linux-arm64.AppImage"
    sha256 "00aa201677366b63c10cc2a77d1fdbe7e8a10d4de1eae66f69a855a95d32b224"
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
