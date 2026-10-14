// Leaflet.draw is an older plugin that expects Leaflet to exist as a global
// variable named "L". Importing this file first makes sure that is true
// before Leaflet.draw loads.
import L from 'leaflet';

window.L = L;

export default L;
