class Cctoken < Formula
  include Language::Python::Virtualenv

  desc "Claude Code token usage monitoring CLI"
  homepage "https://github.com/HongChaeMin/cctoken"
  url "https://github.com/HongChaeMin/cctoken/archive/refs/tags/v1.0.0.tar.gz"
  sha256 ""
  license "MIT"

  depends_on "python@3"

  resource "rich" do
    url "https://files.pythonhosted.org/packages/a1/53/830aa4c21f68608f1e932eba36ac4a3e49b6e21aca2f37e8bbb9e42faab3/rich-14.0.0.tar.gz"
    sha256 "82f1bc23a6a21ebca4ae0c45af9bdcb6f8125b1ce4065f4f0fe5d1a03a83b2e0"
  end

  resource "markdown-it-py" do
    url "https://files.pythonhosted.org/packages/38/71/3b932df36c1a044d397a1f92d1cf91ee0a503d91e470cbd670aa66b07571/markdown-it-py-3.0.0.tar.gz"
    sha256 "e3f60a94fa066dc52ec76661e37c851cb232d92f9886b15cb560aaada2df8feb"
  end

  resource "mdurl" do
    url "https://files.pythonhosted.org/packages/d6/54/cfe61301667036ec958cb99bd3efefba235e65cdeb9c84d24a8293ba1d90/mdurl-0.1.2.tar.gz"
    sha256 "bb413d29f5eea38f31dd4754dd7377d4465116fb207585f97bf925588687c1ba"
  end

  resource "pygments" do
    url "https://files.pythonhosted.org/packages/7c/2d/c3338d48ea6cc0feb8446d8e6937e1408088a72a39937982cc6111d17f84/pygments-2.19.1.tar.gz"
    sha256 "61c16d2a8576dc0649d9f39e089b5f02bcd27fba10d8fb4dcc28173f7a45151f"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "usage: cctoken", shell_output("#{bin}/cctoken --help")
  end
end
