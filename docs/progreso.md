# Reto 2 · La caja negra — Progreso

> **Corte:** 2026-10-10, 19:10. Log: 1.409 líneas, todas con conclusión. Requests usados hoy:
> 1.409 de 8.000. Entrega: 20:00.
>
> **La exploración está cerrada.** No se mandan más requests al original. El servicio cambió una
> sola vez, a las 15:30 (cambio intencional, no habrá otro). El reemplazo se evalúa contra la
> versión vigente a las 20:00, así que todo lo de abajo describe la versión **desde las 15:30**;
> lo anterior queda en [Cambios durante el día](#cambios-durante-el-día-cam).

## 1. Resumen

| Pieza | Estado | Detalle |
| --- | --- | --- |
| Exploración | Cerrada (19:05) | Fases 0–3 antes del cambio; todas repetidas después (833–1304); fase 6 para las dudas finales (1305–1409) |
| Reemplazo (`api/`) | Implementado, sin desplegar | Entrada, control y los 7 comandos. Reproduce todas las secuencias del log posteriores a las 15:30 (`tests/test_log.py`, 454 tests) |
| Despliegue | Sin hacer | Falta la plataforma y `API_TOKEN` con el token del equipo |
| Especificación | Sin empezar | Las 7 secciones del README con `ID \| Comportamiento \| Evidencia \| Confianza` |
| `experimentos.jsonl` | Al día | 1.409 líneas, todas con conclusión |

## 2. Lo que sabemos (versión vigente)

Los números entre paréntesis son `id` de `experimentos.jsonl`.

### Entrada (`ENT`)

- Las rutas que existen (`/msg`, `/health`, `/__reset`) exigen token. Sin token o con token
  inválido: 401 `{"error":"E001","mensaje":"no autorizado"}` (23–26, 55–59). `/health` no es pública.
- Una ruta o un método desconocido da 404 `{"error":"E404","mensaje":"ruta desconocida"}`, incluso
  sin token: la ruta se evalúa antes que el token (46–49, 62–64).
- `GET /health` → 200 `{"ok":true}`; `POST /__reset` → 200 `{"ok":true}`. Un reset sin token no
  borra el estado (59–60).
- Cuerpo: más de 8.192 bytes → 413 `E101 "cuerpo demasiado grande"` (cuenta el cuerpo entero;
  75–93, 1236–1239); JSON inválido o sin cuerpo → 400 `E100 "json inválido"`; sin `m` o `m` que no
  es texto → 400 `E102 "falta m"`; `m` vacío o sin `;` → 400 `E103 "falta control"`; un segmento
  vacío → 400 `E104 "segmento vacío"`. Los campos extra y el `Content-Type` se ignoran.
- Orden: ruta → token → tamaño → JSON → `m` → control → segmentos.
- El header `X-Req` es un contador por token que el reset no reinicia. El evaluador no compara
  headers.

### Integridad: el control (`INT`)

```
N = mensaje sin control, en mayúsculas; A=1 … Z=26, los dígitos igual, todo lo demás se descarta
control = 98 − (100·N mod 97)        → entre 2 y 98
```

- Verificada 20/20 en mensajes nuevos (456–479) y sin cambios tras las 15:30 (882–905).
- Se descartan `;`, `-`, `.`, espacios, í, é, ú y ñ (480–514).
- El control se valida antes que el comando, la aridad y la cuenta (95–98).
- Formato: 1 o 2 cifras. `014`, `100`, `-1`, `+14` o `" 14"` → 400 `E201 "control mal formado"`
  (100–107); un control erróneo → 400 `E202 "control inválido"`.
- `PING` no valida el control: `PING;XX` responde `pong` (109–111).

### Comandos (`COM`)

Los nombres de comando no distinguen mayúsculas (`CONSULTa` 12, `Consulta` 133, `alta` 829); los IDs
de cuenta y de operación sí (`ac-0001` → `E401`, 540; `op-0001` → `E402`, 737).

| Comando | Éxito | Reglas |
| --- | --- | --- |
| `ALTA;nombre` | 201 `{"cuentaId":"AC-0001"}` | Cualquier nombre no vacío: una letra, dígitos, 200 letras, tildes, ñ y espacios (500–508, 533–536) |
| `CONSULTA;cuenta` | 200 `{"cuenta_id":"AC-0001","saldo":"0.00"}` | Saldo como texto con 2 decimales; los montos están en centavos: 40000 → `"400.00"` (841), negativo `"-400.00"` (1121) |
| `DEPOSITO;cuenta;monto` | 200 `{"status":"recieved","operacionId":"OP-0001"}` | Monto: entero de 1 a 9.999.999.999 sin ceros a la izquierda; si no, 400 `E303 "monto inválido"` (518–524, 1301–1302). El máximo es por depósito, no por saldo (1303). `E303` antes que `E401` (1344–1345). Desbloquea la cuenta (ver Memoria) |
| `TRANSFER;origen;destino;monto` | Igual que `DEPOSITO` | Límite de **50.000** por operación: 50.001 → 422 `E506` (922/924, 958/959). Se puede transferir el saldo exacto (922). Misma cuenta → 400 `E304 "origen y destino iguales"` (700) |
| `ANULA;operación` | 200 `{"ok":true,"anulada":"OP-0001"}` | Anula depósitos y transferencias y revierte los saldos, aunque el destino quede en negativo (722–733). Repetida → 200 `{"ok":false,"motivo":"ya anulada"}`. Inexistente → 404 `E402 "operación inexistente"` (734–737) |
| `HALT;x` | — | Con 1 argumento cualquiera (no se valida como cuenta) → 409 `{"error":"E520","mensaje":"operación destructiva: detiene el servicio; reenvía con confirmación"}`, sin efecto en el estado (1310–1319, 1407). Sin argumentos o con 4 → `E302` (830, 1309) |
| `PING` | 200 `{"pong":true}` | No valida el control |

Comando desconocido → 400 `{"error":"E301","mensaje":"comando desconocido "}` (con espacio final).
Si un comando conocido está a distancia de Levenshtein ≤ 2, agrega `"sugerencia":"<COMANDO>"`; con
3, no (817–832). En un empate gana el primero en orden alfabético (`HALTA` → `ALTA`, 832; `HANG` y
`PILT` → `HALT`, 1346–1347). Aridad incorrecta → 400 `E302 "aridad inválida"`.

### Memoria entre requests (`MEM`)

- Cuentas `AC-0001`, `AC-0002`… y operaciones `OP-0001`… en orden. Los rechazos no consumen número
  (ejemplos 2–3, 134–135, 636). `ANULA` tampoco (ejemplos 13–18).
- **Bloqueo:** cada cuenta de origen lleva un contador de `E506`/`E507` seguidos. Al llegar a 3, toda
  transferencia que sale de ella da 423 `{"error":"E510","mensaje":"cuenta bloqueada","intentos":N}`
  (1075, 1103, 1134). Solo una transferencia exitosa reinicia el contador (647–649). `E303`, `E304`
  y `E401` no suman ni reinician (757–791).
- **`intentos`:** cuántos `E510` lleva la cuenta, desde 1 y sin tope (1199–1203, 1328–1333,
  1376–1382). Es por cuenta (1341). `E303`, `E304` y `E401` en la cuenta bloqueada no lo suben
  (1200–1201, 1330).
- **Desbloqueo:** un `DEPOSITO` en la propia cuenta bloqueada la desbloquea y reinicia sus contadores;
  si se vuelve a bloquear, `intentos` empieza en 1 (1335–1336, 1355–1357, 1396–1401). No desbloquean:
  un depósito en otra cuenta (1391–1392), una transferencia entrante (1393–1394) ni `CONSULTA`
  (1366–1368).
- Una cuenta bloqueada puede consultar, recibir depósitos y transferencias, y anular sus operaciones
  (635–638, 747). Las demás cuentas no se ven afectadas.

### Orden de errores (`ERR`)

```
entrada → control (E201/E202) → comando (E301) → aridad (E302)
DEPOSITO: E303 monto → E401 cuenta
TRANSFER: E303 monto → E304 misma cuenta → E401 cuenta → E510 bloqueada → E506 límite → E507 saldo
```

Evidencia: 95–98, 606, 704–707, 796–803, 812–815, 862, 1199–1203, 1330, 1344–1345.

### Cambios durante el día (`CAM`)

Detectado al repetir la línea base a las 18:15; comparado con `explorador diferencias 15:30`.

| Regla | Antes de las 15:30 | Desde las 15:30 | Evidencia (antes → ahora) |
| --- | --- | --- | --- |
| Saldo en `CONSULTA` | Número entero: `"saldo":40000` | Texto con 2 decimales, el monto en centavos: `"saldo":"400.00"`, `"0.00"` | 9 → 841, 6 → 838, 523 → 942 |
| Saldo negativo (tras `ANULA`) | `-40000` | `"-400.00"` | 733 → 1121 |
| Límite de `TRANSFER` | 100.000 por operación | 50.000 por operación | 11 → 843, 136 → 862, 699 → 924; borde 958/959 |
| `E510` cuenta bloqueada | 409 `{"error":"E510","mensaje":"cuenta bloqueada"}` | 423 y `"intentos":N` | 634 → 1075, 811/814/815 → 1199/1202/1203 |

Sin cambios (todas las fases repetidas, 833–1304): entrada, tamaño máximo, control, validación y
máximo de montos, numeración, contador de bloqueo, `ANULA`, orden de errores y sugerencias. El
desbloqueo por depósito, `E520` e `intentos` sin tope solo se probaron después del cambio.

### Riesgos (`RIE`)

- `ANULA` deja el destino con saldo negativo si ya gastó el dinero (731–733, 1119–1121).
- `HALT` pide confirmación para "detener el servicio". La confirmación no se probó a propósito.
- Defectos que hay que copiar: `"recieved"`, el espacio final en `"comando desconocido "`,
  `cuentaId` frente a `cuenta_id`, los fallos de `ANULA` con status 200 y `E520` con 409.

## 3. Supuestos (sin evidencia, implementados con un comportamiento por defecto)

| Supuesto | Implementación en `api/` |
| --- | --- |
| Cómo se confirma `HALT` | Todo `HALT` con 1 argumento responde `E520` |
| `HALT` con 2 o 3 argumentos | `E302` (solo se probaron 0 y 4) |
| `PING` con argumentos | `pong` (no probado, por decisión) |
| Límite acumulado de `TRANSFER` | No existe (con 80.000 ya supera el límite por operación y no se puede aislar) |

## 4. Pendiente

| Tarea | Detalle |
| --- | --- |
| **Desplegar el reemplazo** | Plataforma por definir. Un solo proceso; `API_TOKEN` = token del equipo (no el personal del `.env`) |
| **Especificación** | Las 7 secciones del README. Esta página es la base: cada regla ya tiene su evidencia |
| `PING` sin control | Fuera de alcance por decisión |

Herramientas: `uv run pytest` en `api/` corre el replay del log; `uv run explorador diferencias 15:30`
compara corridas antes y después del cambio.
