from setuptools import setup

setup(
    name="cliperino",
    version="1.0.0",
    description="A GTK Clipboard Manager with history and search capabilities",
    long_description="A modern clipboard manager that allows you to search through your clipboard history and easily copy previous items.",
    author="Silicon Squire",
    author_email="discs@siliconsquire.com",
    url="https://github.com/SiliconSquire/cliperino",
    packages=["cliperino"],
    install_requires=[
        "python3-gobject",
        "python3-cairo",
        "gir1.2-gtk-3.0",
        "python3-keybinder",
    ],
    data_files=[
        ("share/applications", ["share/applications/cliperino.desktop"]),
        (
            "share/icons/hicolor/48x48/apps",
            ["share/icons/hicolor/48x48/apps/cliperino.svg"],
        ),
        (
            "share/icons/hicolor/64x64/apps",
            ["share/icons/hicolor/64x64/apps/cliperino.svg"],
        ),
        (
            "share/icons/hicolor/128x128/apps",
            ["share/icons/hicolor/128x128/apps/cliperino.svg"],
        ),
        ("bin", ["bin/cliperino"]),
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: X11 Applications :: GTK",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Topic :: Utilities",
    ],
)
