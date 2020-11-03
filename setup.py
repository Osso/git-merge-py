from setuptools import (find_packages,
                        setup)

setup(name="gitmergepy", packages=find_packages(),
      dependency_links=['http://github.com/Osso/redbaron/tarball/master#egg=redbaron-1.0'])
