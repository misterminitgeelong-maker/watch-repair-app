/* All content is bundled. Only raster tiles are requested remotely; job text stays in this local document. */
(function () {
  'use strict';
  var map = L.map('map', { zoomControl: true, scrollWheelZoom: true, attributionControl: true }).setView([-37.8136, 144.9631], 5);
  var tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    minZoom: 0, maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'
  }).addTo(map);
  var error = document.getElementById('tile-error');
  tiles.on('tileerror', function () { error.style.display = 'block'; });
  tiles.on('tileload', function () { error.style.display = 'none'; });
  var layers = L.layerGroup().addTo(map), positions = [], signature = '';
  function fit() {
    if (positions.length === 1) map.setView(positions[0], 14);
    else if (positions.length > 1) map.fitBounds(positions, { padding: [34, 34], maxZoom: 15 });
    else map.setView([-37.8136, 144.9631], 5);
  }
  var Fit = L.Control.extend({ onAdd: function () {
    var box = L.DomUtil.create('div', '');
    var button = document.createElement('button'); button.type = 'button'; button.className = 'map-fit'; button.textContent = 'Fit stops'; button.setAttribute('aria-label', 'Fit all route stops');
    box.appendChild(button); L.DomEvent.disableClickPropagation(box); button.addEventListener('click', fit); return box;
  }}); new Fit({ position: 'topright' }).addTo(map);
  function text(parent, tag, value) { var el = document.createElement(tag); el.textContent = value || ''; parent.appendChild(el); return el; }
  function action(parent, label, method, id) {
    var button = document.createElement('button'); button.type = 'button'; button.textContent = label;
    button.addEventListener('click', function () { if (window.MainspringMap && typeof window.MainspringMap[method] === 'function') window.MainspringMap[method](id); }); parent.appendChild(button);
  }
  window.renderStops = function (input) {
    var pins = Array.isArray(input) ? input.filter(function (p) { return p && Number.isFinite(p.lat) && Number.isFinite(p.lng) && Math.abs(p.lat) <= 85.05112878 && Math.abs(p.lng) <= 180; }).slice(0, 100) : [];
    layers.clearLayers(); positions = pins.map(function (p) { return [p.lat, p.lng]; });
    var grouped = new Map();
    pins.forEach(function (p) { var key = p.lat + ',' + p.lng; if (!grouped.has(key)) grouped.set(key, []); grouped.get(key).push(p); });
    grouped.forEach(function (group) {
      var label = document.createElement('span'); label.className = 'stop-pin'; label.textContent = group.map(function (p) { return p.order; }).join(', ');
      var popup = document.createElement('div');
      group.forEach(function (p) { text(popup, 'strong', p.order + '. ' + p.label); text(popup, 'p', p.address); text(popup, 'p', p.status); action(popup, 'Open job', 'openJob', p.id); action(popup, 'Navigate', 'navigate', p.id); });
      L.marker([group[0].lat, group[0].lng], { icon: L.divIcon({ html: label, className: '', iconSize: [34, 34], iconAnchor: [17, 17] }) }).bindPopup(popup).addTo(layers);
    });
    if (positions.length > 1) L.polyline(positions, { color: '#a4592d', weight: 3, dashArray: '7 7', opacity: 0.75, interactive: false }).addTo(layers);
    var next = pins.map(function (p) { return p.id + ':' + p.lat + ':' + p.lng; }).join('|');
    if (next !== signature) { signature = next; fit(); }
    map.invalidateSize(); document.documentElement.setAttribute('data-stops', String(pins.length));
    if (window.MainspringMap) window.MainspringMap.ready(pins.length);
  };
})();
