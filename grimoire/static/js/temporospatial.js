var map = new Datamap({
    element: document.getElementById('map'),
    fills: {
        defaultFill: '#677077',
        publication: '#f2b632',
        birth: '#677077',
        death: '#181b2c',
    },
    setProjection: function(element) {
        var projection = d3.geo.mercator()
            .center([-15, 44])
            .rotate([4.4, 0])
            .scale(400)
            .translate([element.offsetWidth / 2, element.offsetHeight / 2]);
        var path = d3.geo.path()
            .projection(projection);
        return {path: path, projection: projection};
    },
    geographyConfig: {
        highlightOnHover: false,
        popupOnHover: false,
    },
});

map.bubbles(events, {
    popupTemplate: function (geo, data) {
        return ['<div class="hoverinfo">',
            data.identifier,
            '<br>' + data.place + ', ' + data.year,
        '</div>'].join('');
    }
});
