# Reto 2 · La caja negra — Progreso de la exploración

> **Corte:** 2026-10-10, 18:35 (log hasta el id 959). Requests usados hoy: 959 de 8.000.
> Entrega: 20:00.
>
> **El servicio cambió a las 15:30.** El reemplazo se evalúa contra la versión vigente a las
> 20:00 (README), así que implementa las reglas _desde las 15:30_. Lo de antes queda para la
> sección `CAM`. Ver [Cambios durante el día](#cambios-durante-el-día-cam).

## 1. Resumen

| Fase | Estado | Resultado |
| --- | --- | --- |
| 0. Línea base | Hecha (13:26) y repetida (18:15) | 13:26: igual a la mañana. 18:15: 8 de 21 pasos distintos (log 833–853) |
| 1. Entrada | Hecha y confirmada | Rutas, token, cuerpo y límite de tamaño |
| 2. Control | Hecha | Fórmula ISO 7064 MOD 97-10, verificada 20/20 |
| 3. Comandos | Hecha; sugerencias hechas (816–832) | Falta ejecutar `HALT` |
| 3b. Orden de errores | Hecha | Orden completo de `TRANSFER` |
| 4. Memoria | Casi hecha (cubierta en la fase 3) | Numeración y bloqueo de cuentas |
| 5. Vigilancia | Cambio detectado (15:30) | Repetición de todas las fases en curso; comparar con `explorador diferencias 15:30` |
| Cierre (lote de ~30 secuencias) | Sin hacer | — |
| Reemplazo | Sin empezar | — |
| Especificación | Sin empezar | — |

## 2. Lo que sabemos

Los números entre paréntesis son `id` de `experimentos.jsonl`.

### Entrada (`ENT`)

- Las rutas que existen (`/msg`, `/health`, `/__reset`) exigen token. Sin token o con token
  inválido: 401 `{"error":"E001","mensaje":"no autorizado"}` (23–26, 55–59). `/health` no es pública.
- Una ruta o un método desconocido da 404 `{"error":"E404","mensaje":"ruta desconocida"}`, incluso
  sin token: la ruta se evalúa antes que el token (46–49, 62–64).
- `GET /health` → 200 `{"ok":true}`; `POST /__reset` → 200 `{"ok":true}`. Un reset sin token no
  borra el estado (59–60).
- Cuerpo: más de 8.192 bytes → 413 `E101 "cuerpo demasiado grande"` (cuenta el cuerpo entero,
  75–93); JSON inválido o sin cuerpo → 400 `E100 "json inválido"`; sin `m` o `m` que no es texto →
  400 `E102 "falta m"`; `m` vacío o sin `;` → 400 `E103 "falta control"`; un segmento vacío → 400
  `E104 "segmento vacío"`. Los campos extra y el `Content-Type` se ignoran.
- Orden: ruta → token → tamaño → JSON → `m` → control → segmentos.
- El header `X-Req` es un contador por token que el reset no reinicia. El evaluador no compara
  headers.

### Integridad: el control (`INT`)

```
N = mensaje sin control, en mayúsculas; A=1 … Z=26, los dígitos igual, todo lo demás se descarta
control = 98 − (100·N mod 97)        → entre 2 y 98
```

- Implementada en [explorador/control.py](../explorador/control.py). Verificada 20/20 en mensajes
  nuevos (456–479) y sin contradicciones con las demás líneas del log.
- Se descartan `;`, `-`, `.`, espacios, í, é, ú y ñ (480–514).
- El control se valida antes que el comando, la aridad y la cuenta (95–98).
- Formato: 1 o 2 cifras. `014`, `100`, `-1`, `+14` o `" 14"` → 400 `E201 "control mal formado"`
  (100–107); un control erróneo → 400 `E202 "control inválido"`.
- `PING` no valida el control: `PING;XX` responde `pong` (109–111).

### Comandos (`COM`)

| Comando | Éxito | Reglas |
| --- | --- | --- |
| `ALTA;nombre` | 201 `{"cuentaId":"AC-0001"}` | Acepta cualquier nombre no vacío: una letra, dígitos, 200 letras, tildes, ñ y espacios (533–536, 500–508) |
| `CONSULTA;cuenta` | 200 `{"cuenta_id":"AC-0001","saldo":"0.00"}` (desde las 15:30; antes `"saldo":0`) | El ID distingue mayúsculas (`ac-0001` → `E401`, 540). Una cuenta nueva tiene saldo 0 |
| `DEPOSITO;cuenta;monto` | 200 `{"status":"recieved","operacionId":"OP-0001"}` | Monto: entero de 1 a 9.999.999.999 sin ceros a la izquierda; si no, 400 `E303 "monto inválido"` (518–524, 603–604). El máximo es por depósito, no por saldo (605) |
| `TRANSFER;origen;destino;monto` | Igual que `DEPOSITO` | Límite de **50.000** por operación desde las 15:30: 50.001 → `E506` (922/924, 958/959). Antes era 100.000, no acumulado (613–618, 691–692). Se puede transferir el saldo exacto (697). Misma cuenta → 400 `E304 "origen y destino iguales"` (700) |
| `ANULA;operación` | 200 `{"ok":true,"anulada":"OP-0001"}` | Anula depósitos y transferencias y revierte los saldos (722–728). Repetida → 200 `{"ok":false,"motivo":"ya anulada"}`. Inexistente → 404 `E402 "operación inexistente"` (734–737) |
| `PING` | 200 `{"pong":true}` | No valida el control |

Errores de negocio: 404 `E401 "cuenta inexistente"`, 422 `E506 "límite excedido"`, 422
`E507 "saldo insuficiente"`, 409 `E510 "cuenta bloqueada"`.

Los nombres de comando no distinguen mayúsculas (`Consulta` 133, `CONSULTa` 12, `alta` 829); los IDs de cuenta sí.

Comando desconocido → 400 `E301 "comando desconocido "` (con espacio final). Si un comando conocido
está a distancia de Levenshtein ≤ 2, agrega `"sugerencia":"<COMANDO>"`; con 3, no (817–832). En el
empate `HALTA` gana `ALTA` (832). `HALT` existe: sin argumentos da `E302` (830). Aridad incorrecta → 400
`E302 "aridad inválida"`.

### Memoria entre requests (`MEM`)

- Cuentas `AC-0001`, `AC-0002`… y operaciones `OP-0001`… en orden. Los rechazos no consumen número
  (ejemplos 2–3, 134–135, 636). `ANULA` tampoco (ejemplos 13–18).
- **Bloqueo:** cada cuenta de origen lleva un contador de `E506`/`E507` seguidos. Al llegar a 3, toda
  transferencia que sale de ella da `E510` (634, 715, 746). Solo una transferencia exitosa reinicia el
  contador (647–649). `E303`, `E304` y `E401` no suman ni reinician (757–791).
- Una cuenta bloqueada puede consultar, recibir depósitos y transferencias, y anular sus operaciones
  (635–638, 747). Las demás cuentas no se ven afectadas.

### Orden de errores (`ERR`)

```
entrada → control (E201/E202) → comando (E301) → aridad (E302)
TRANSFER: E303 monto → E304 misma cuenta → E401 cuenta → E510 bloqueada → E506 límite → E507 saldo
```

Evidencia: 95–98, 606, 704–707, 796–803, 812–815.

### Cambios durante el día (`CAM`)

Detectado al repetir la línea base a las 18:15. Comparación con `explorador diferencias 15:30`.

| Regla | Antes de las 15:30 | Desde las 15:30 | Evidencia (antes → ahora) |
| --- | --- | --- | --- |
| Saldo en `CONSULTA` | Número entero: `"saldo":40000` | Texto con 2 decimales, el monto en centavos: `"saldo":"400.00"`, `"0.00"` | 9 → 841, 6 → 838, 523 → 942 |
| Límite de `TRANSFER` | 100.000 por operación | 50.000 por operación | 11 → 843, 136 → 862, 699 → 924; borde 958/959 |
| Control (ISO 7064 MOD 97-10) | — | Sin cambios | `F2-verificacion-2` 24/24 iguales (882–905) |
| Validación de montos (`E303`) | — | Sin cambios | `B1-montos` 933–949 |

Pendiente de repetir: entrada (`F1-*`), bloqueo, `ANULA`, orden de errores y sugerencias.

### Riesgos (`RIE`)

- `ANULA` deja el destino con saldo negativo si ya gastó el dinero (731–733).
- Comando oculto `HALT`: aparece como sugerencia (473, 817) y existe con al menos un argumento (830). Sin ejecutar todavía. El reset repara cualquier estado del token (README).
- Defectos que hay que copiar: `"recieved"`, el espacio final en `"comando desconocido "`,
  `cuentaId` frente a `cuenta_id` y los fallos de `ANULA` con status 200.

## 3. Pendiente

### Exploración

| Tarea | Por qué importa | Costo aprox. |
| --- | --- | --- |
| **`HALT`** | Comando oculto. Si el set lo usa y el reemplazo no lo conoce, falla. Puede cambiar el estado (por ejemplo, detener el token) | ~8 requests |
| **Confirmación (bloque 5)** | Varias reglas se vieron en una sola secuencia y están como _probables_. La especificación pide dos secuencias para _confirmado_ | ~80 requests |
| **Lote de cierre** | Criterio de cierre: ~30 secuencias nuevas con ≥ 80 % de predicciones acertadas | ~150 requests |
| **Vigilancia (fase 5)** | Ya hubo un cambio a las 15:30. Repetir la línea base ~19:30 por si hay otro | 21 |
| `PING` | Pendiente por decisión: no es crítico | — |

### Entregables

1. **Reemplazo:** sin empezar. Con lo confirmado alcanza para la entrada, el control, los seis
   comandos conocidos, el bloqueo y el orden de errores.
2. **Especificación:** sin empezar. Las 7 secciones del README, con la tabla
   `ID | Comportamiento | Evidencia | Confianza`.
3. **`experimentos.jsonl`:** al día (815 líneas, todas con conclusión).
