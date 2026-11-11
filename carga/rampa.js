// Prueba en rampa: sube los usuarios por escalones (10, 25, 50, 100) y
// sostiene cada escalon 90 s para encontrar el punto de quiebre.
// Misma mezcla de peticiones que humo.js para que los numeros sean comparables.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.2/index.js';

const BASE_URL = __ENV.BASE_URL || 'http://api:8000';
const imagen = open('/imagenes_prueba/pequena.jpg', 'b');

// Peticiones que tarden mas de 60 s cuentan como fallo (timeout del cliente).
const PARAMS = (endpoint) => ({ tags: { endpoint }, timeout: '60s' });

export const options = {
  scenarios: {
    rampa: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 10 },
        { duration: '90s', target: 10 },
        { duration: '30s', target: 25 },
        { duration: '90s', target: 25 },
        { duration: '30s', target: 50 },
        { duration: '90s', target: 50 },
        { duration: '30s', target: 100 },
        { duration: '90s', target: 100 },
      ],
      gracefulRampDown: '30s',
    },
  },
  summaryTrendStats: ['avg', 'min', 'p(50)', 'p(90)', 'p(95)', 'p(99)', 'max'],
  thresholds: {
    'http_req_duration{endpoint:procesar}': ['p(99)>=0'],
    'http_req_duration{endpoint:subir}': ['p(99)>=0'],
    'http_req_duration{endpoint:historial}': ['p(99)>=0'],
    'http_req_failed{endpoint:procesar}': ['rate>=0'],
    'http_req_failed{endpoint:subir}': ['rate>=0'],
    'http_req_failed{endpoint:historial}': ['rate>=0'],
  },
};

export default function () {
  const r1 = http.post(`${BASE_URL}/procesar`,
    { archivo: http.file(imagen, 'pequena.jpg', 'image/jpeg') }, PARAMS('procesar'));
  check(r1, { 'procesar status 200': (r) => r.status === 200 });

  const r2 = http.post(`${BASE_URL}/subir`,
    { archivo: http.file(imagen, 'pequena.jpg', 'image/jpeg') }, PARAMS('subir'));
  check(r2, { 'subir status 200': (r) => r.status === 200 });

  const r3 = http.get(`${BASE_URL}/historial`, PARAMS('historial'));
  check(r3, { 'historial status 200': (r) => r.status === 200 });

  sleep(0.5);
}

export function handleSummary(data) {
  const nombre = __ENV.ETIQUETA ? `${__ENV.ETIQUETA}.json` : 'rampa.json';
  return {
    stdout: textSummary(data, { indent: ' ', enableColors: false }),
    [`/carga/resultados/${nombre}`]: JSON.stringify(data, null, 2),
  };
}
