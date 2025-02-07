# -*- coding: utf-8 -*-
"""
Created on Fri Feb  7 10:57:06 2025

@author: Sherlyds
"""

from flask import Flask, jsonify
import os

from Registration_frontend_v2 import register


app = Flask(__name__)

register(app)


if __name__ == '__main__':
    app.run()