#!/bin/bash

source bin/activate
python build_static.py

cp -r grimoire/static _site/
uglifyjs grimoire/static/temporospatial.js > _site/static/temporospatial.js
cssnano < grimoire/static/styles/app.css > _site/static/styles/app.css
