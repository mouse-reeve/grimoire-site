#!/bin/bash

set -e

source bin/activate
python build_static.py

cp -r grimoire/static _site/
uglifyjs grimoire/static/js/temporospatial.js > _site/static/js/temporospatial.js
cssnano < grimoire/static/styles/app.css > _site/static/styles/app.css
