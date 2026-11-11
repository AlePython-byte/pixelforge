// Prueba de memoria: solo /subir con la imagen mediana (3000x2000), subiendo
// las peticiones simultaneas (2, 4, 8, 12, 16) hasta que el contenedor
// supere su limite de RAM y el kernel lo mate (OOM killer).
import http from 'k6/http';
import { check, sleep } from 'k6';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.2/index.js';

const BASE_URL = __ENV.BASE_URL || 'http://api:8000';
const imagen = open('/imagenes_prueba/mediana.jpg', 'b');

export const options = {
  scenarios: {
    memoria: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 2 },
        { duration: '30s', target: 2 },
        { duration: '10s', target: 4 },
        { duration: '30s', target: 4 },
        { duration: '10s', target: 8 },
        { duration: '30s', target: 8 },
        { duration: '10s', target: 12 },
        { duration: '30s', target: 12 },
        { duration: '10s', target: 16 },
        { duration: '30s', target: 16 },
      ],
      gracefulRampDown: '10s',
    },
  },
  summaryTrendStats: ['avg', 'min', 'p(50)', 'p(90)', 'p(95)', 'p(99)', 'max'],
  thresholds: {
    'http_req_duration{endpoint:subir}': ['p(99)>=0'],
    'http_req_failed{endpoint:subir}': ['rate>=0'],
  },
};

export default function () {
  const r = http.post(`${BASE_URL}/subir`,
    { archivo: http.file(imagen, 'mediana.jpg', 'image/jpeg') },
    { tags: { endpoint: 'subir' }, timeout: '60s' });
  check(r, { 'subir status 200': (x) => x.status === 200 });
  // Si la API murio, no inundar los datos con miles de errores por segundo.
  if (r.status !== 200) sleep(1);
}

export function handleSummary(data) {
  const nombre = __ENV.ETIQUETA ? `${__ENV.ETIQUETA}.json` : 'memoria.json';
  return {
    stdout: textSummary(data, { indent: ' ', enableColors: false }),
    [`/carga/resultados/${nombre}`]: JSON.stringify(data, null, 2),
  };
}
