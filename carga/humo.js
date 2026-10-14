// Prueba de humo: 5 usuarios virtuales durante 1 minuto sobre los 3 endpoints.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.2/index.js';

const BASE_URL = __ENV.BASE_URL || 'http://api:8000';

// open() solo funciona en la fase de init; lee el archivo una vez en binario.
const imagen = open('/imagenes_prueba/pequena.jpg', 'b');

export const options = {
  vus: 5,
  duration: '1m',
  // Percentiles que aparecerán en el resumen y en el JSON (p50 = mediana).
  summaryTrendStats: ['avg', 'min', 'p(50)', 'p(90)', 'p(95)', 'p(99)', 'max'],
  // Umbrales "siempre verdaderos": solo sirven para que k6 muestre
  // percentiles por endpoint en el resumen. No hacen fallar la prueba.
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
  const r1 = http.post(
    `${BASE_URL}/procesar`,
    { archivo: http.file(imagen, 'pequena.jpg', 'image/jpeg') },
    { tags: { endpoint: 'procesar' } },
  );
  check(r1, { 'procesar status 200': (r) => r.status === 200 });

  const r2 = http.post(
    `${BASE_URL}/subir`,
    { archivo: http.file(imagen, 'pequena.jpg', 'image/jpeg') },
    { tags: { endpoint: 'subir' } },
  );
  check(r2, { 'subir status 200': (r) => r.status === 200 });

  const r3 = http.get(`${BASE_URL}/historial`, { tags: { endpoint: 'historial' } });
  check(r3, { 'historial status 200': (r) => r.status === 200 });

  sleep(0.5);
}

// Resumen en pantalla + JSON crudo con fecha y hora (UTC) en el nombre.
export function handleSummary(data) {
  const sello = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  return {
    stdout: textSummary(data, { indent: ' ', enableColors: false }),
    [`/carga/resultados/humo_${sello}.json`]: JSON.stringify(data, null, 2),
  };
}
