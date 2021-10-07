from setuptools import (find_packages,
                        setup)

setup(name="gitmergepy", packages=find_packages(),
      install_requires=["redbaron==1.0",
                        "python-Levenshtein==0.12.2",
                        "diff-match-patch==20200713"],
      dependency_links=['http://github.com/Osso/redbaron/tarball/master#egg=redbaron-1.0'])
