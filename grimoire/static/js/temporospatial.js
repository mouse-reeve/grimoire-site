var daterange = 20;

var map = new Datamap({
    element: document.getElementById('map'),
    fills: {
        defaultFill: '#677077',
        publication: '#f2b632',
        birth: '#677077',
        death: '#181b2c',
        trial: '#2c181b',
        era: '#fefefe',
    },
    setProjection: function(element) {
        var projection = d3.geo.mercator()
            .center([-15, 50])
            .rotate([4.4, 0])
            .scale(400)
            .translate([element.offsetWidth / 2, element.offsetHeight / 2]);
        var path = d3.geo.path()
            .projection(projection);
        return {path: path, projection: projection};
    },
    geographyConfig: {
        highlightOnHover: false,
        popupOnHover: true,
    },
});

var populateMap = function (eventset) {
    map.bubbles(eventset, {
        popupTemplate: function (geo, data) {
            return ['<div class="hoverinfo">',
                data.identifier,
                '<br>' + data.place + ', ' + data.display_date,
                (data.end_year ? ' - ' + data.end_year : ''),
                '</div>'].join('');
        }
    });
};

var setDate = function () {
    var year = $('#date-slider').val();
    $('#date-input').val(year);
    setEvents(parseInt(year));
};

var setDateSlider = function () {
    var year = $('#date-input').val();
    $('#date-slider').val(year);
    setEvents(parseInt(year));
};

var setEvents = function (year) {
    var eventset = [];

    var coords = {};
    $.each(events, function (index, item) {
        if (item.year && !item.end_year) {
            if (item.year < year + daterange && item.year > year - daterange) {
                coords[item.latitude + ',' + item.longitude] = coords[item.latitude + ',' + item.longitude] ? coords[item.latitude + ',' + item.longitude] + 1 : 1;
                eventset.push(item);
            }
        } else if (item.year && item.end_year) {
            if ((item.year < year + daterange && item.year > year - daterange) ||
                (item.end_year < year + daterange && item.end_year > year - daterange) ||
                (item.year < year - daterange && item.end_year > year + daterange )) {
                coords[item.latitude + ',' + item.longitude] = coords[item.latitude + ',' + item.longitude] ? coords[item.latitude + ',' + item.longitude] + 1 : 1;
                eventset.push(item);
            }
        }
    });
    if (eventset.length < 4) {
        $.each(events, function (index, item) {
            if (item.year < year + daterange) {
                eventset.push(item);
            }
            if (eventset.length > 3) {
                return false;
            }
        });
    }

    // shuffle nodes that are on top of each other
    $.each(eventset, function (index, item) {
        var key = item.latitude + ',' + item.longitude;
        if (coords[key] > 1) {
            coords[key] -= 1;
            item.latitude += coords[key] / 2;
            item.longitude += coords[key] / 2;
        }
    });
    $('#current-dates').html(year-daterange + ' - ' + (year+daterange));
    populateMap(eventset);
};

var year = 1590;
$('#date-input').val(year);
$('#date-slider').val(year);
setEvents(year);
