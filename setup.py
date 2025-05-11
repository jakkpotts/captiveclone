"""
Setup script for CaptiveClone.
"""

from setuptools import setup, find_packages

setup(
    name="captiveclone",
    version="1.0.0",
    description="A network security assessment tool for captive portal analysis",
    author="The CaptiveClone Team",
    packages=find_packages(),
    install_requires=[
        "scapy>=2.4.5",
        "netifaces>=0.11.0",
        "wifi>=0.0.0",
        "pyric>=0.1.6.3",
        "pywifi>=1.1.12",
        "sqlalchemy>=1.4.0",
        "alembic>=1.7.5",
        "prompt_toolkit>=3.0.24",
        "rich>=10.16.1",
        "requests>=2.26.0",
        "pyyaml>=6.0",
        "python-dotenv>=0.19.2",
        "beautifulsoup4>=4.10.0",
        "selenium>=4.1.0",
        "webdriver-manager>=3.5.2",
        "mitmproxy>=8.0.0",
        "pillow>=9.0.0",
        "dnspython>=2.1.0",
        "pyshark>=0.4.5",
        "werkzeug>=2.0.0",
        "flask>=2.0.0",
        "flask-socketio>=5.1.1",
        "eventlet>=0.33.0",
        "passlib>=1.7.4",
        "argon2-cffi>=21.3.0",
        "python-engineio>=4.3.1",
        "python-socketio>=5.5.0",
        "gevent-websocket>=0.10.1",
        "bidict>=0.22.0",
        "flask-cors>=3.0.10",
        "plotly>=5.8.0",
        "pandas>=1.4.2",
        "flask-login>=0.6.0",
        "cryptography>=38.0.0",
        "jinja2>=3.1.2",
    ],
    entry_points={
        "console_scripts": [
            "captiveclone=captiveclone.captiveclone:main",
        ],
    },
    python_requires=">=3.7",
) 