class Provara < Formula
  include Language::Python::Virtualenv

  desc "Self-sovereign cryptographic event log protocol"
  homepage "https://github.com/provara-protocol/provara"
  url "https://files.pythonhosted.org/packages/70/79/e55dd15c7790244e4d7cfd19f5f7a9a4d8b5b7f24db118dfaab942b4caab/provara_protocol-1.0.0.tar.gz"
  sha256 "80c5c879ec325886a3f467f0cda61557327c15a09994788236f8753d6cd72a89"
  license "Apache-2.0"

  depends_on "python@3.12"

  resource "cryptography" do
    url "https://files.pythonhosted.org/packages/a7/35/c495bffc2056f2dadb32434f1feedd79abde2a7f8363e1974afa9c33c7e2/cryptography-45.0.7.tar.gz"
    sha256 "4b1654dfc64ea479c242508eb8c724044f1e964a47d1d1cacc5132292d851971"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "Provara Protocol CLI", shell_output("#{bin}/provara --help")
  end
end
