# Especificación del servicio "caja negra"

Este documento permite reimplementar el servicio sin tocar el original. Describe la **versión 2**,
vigente desde las 15:30 del 2026-10-10. Lo que cambió respecto de la versión 1 está en la sección [6. Cambios durante el día](#6-cambios-durante-el-día-cam).

- **Evidencia**: números `id` de `experimentos.jsonl`. Los `id` 1–832 son de la versión 1
  (antes de las 15:30) y los 833–1409 de la versión 2. Cuando un comportamiento no cambió se citan
  los dos tramos.
- **Confianza**: **confirmado** quiere decir que se probó en dos o más secuencias distintas con el
  mismo resultado. **Probable** quiere decir que se vio en una sola secuencia o que se infiere.
  **Supuesto** quiere decir que no se probó y que el reemplazo hace eso por defecto.
- **Montos**: son enteros en centavos. `CONSULTA` los muestra divididos por 100 y con 2 decimales.
- **Errores del original que hay que copiar**: algunas respuestas del servicio tienen errores de
  redacción. El reemplazo tiene que repetirlos tal cual, porque se compara letra por letra y
  corregirlos hace fallar la respuesta:
  - `"recieved"`, mal escrito (debería ser `"received"`): `DEPOSITO` y `TRANSFER` (COM-DEPOSITO-01).
  - `"comando desconocido "` termina con un espacio de más (COM-03).
  - `ALTA` responde `cuentaId` y `CONSULTA` responde `cuenta_id` para el mismo dato
    (COM-ALTA-01, COM-CONSULTA-01).

---

## 1. Entrada (`ENT`)

Es todo lo que el servicio revisa **antes** de mirar el comando: a qué ruta se llamó, si viene el
token y si el cuerpo tiene la forma esperada (`{"m": "..."}`, con al menos un `;` y sin segmentos
vacíos). Si algo falla en esta etapa, responde con un error y el comando no llega a ejecutarse.

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| ENT-01 | Hay tres rutas: `POST /msg` (mensajes), `GET /health` y `POST /__reset`. | 967, 968, 960 (antes 2, 30, 1) | confirmado |
| ENT-02 | En una ruta que existe, si no hay header `Authorization: Bearer <token>` o el token no es válido, responde **401** `{"error":"E001","mensaje":"no autorizado"}`. | 961, 962, 993, 994 (antes 23, 24, 55, 56) | confirmado |
| ENT-03 | `/health` **no es pública**: sin token o con un token inválido da 401 `E001`. Con token responde 200 `{"ok":true}`. | 963, 995, 996; 968, 999, 1404 (antes 25, 57, 58; 30, 61) | confirmado |
| ENT-04 | `POST /__reset` con token responde 200 `{"ok":true}` y borra todo el estado: no quedan cuentas ni operaciones y la numeración vuelve a `AC-0001` y `OP-0001`. | 965–966, 1402–1406 | confirmado |
| ENT-05 | `POST /__reset` sin token da 401 `E001` y **no** borra el estado. | 997–998 (antes 59–60) | confirmado |
| ENT-06 | Una ruta desconocida, con cualquier método, responde **404** `{"error":"E404","mensaje":"ruta desconocida"}`. | 984, 985, 1000 (antes 46, 47, 62) | confirmado |
| ENT-07 | Un método no soportado en una ruta que existe (`GET /msg`, `DELETE /health`) también da 404 `E404`, no 405. | 986, 1001 (antes 48, 63) | confirmado |
| ENT-08 | La ruta se evalúa antes que el token: una ruta desconocida sin token o con un token inválido da 404 `E404`, no 401. | 987, 1002 (antes 49, 64) | confirmado |
| ENT-09 | Un cuerpo de más de **8.192 bytes** responde **413** `{"error":"E101","mensaje":"cuerpo demasiado grande"}`. 8.192 bytes se aceptan y 8.193 no. Cuenta el cuerpo entero, con los campos extra. | 1236–1237, 1238–1239, 1222–1234 (antes 89–93) | confirmado |
| ENT-10 | Un JSON mal formado o un cuerpo vacío responde 400 `{"error":"E100","mensaje":"json inválido"}`. | 970, 978, 1003, 1009 (antes 32, 40, 65, 71) | confirmado |
| ENT-11 | Si el cuerpo no es un objeto (array, string, número), si falta `m` o si `m` no es texto (número, `null`, objeto), responde 400 `{"error":"E102","mensaje":"falta m"}`. | 971, 973, 974, 976, 977, 1004, 1006, 1008 | confirmado |
| ENT-12 | Si `m` está vacío o no tiene ningún `;`, responde 400 `{"error":"E103","mensaje":"falta control"}`. | 972, 980, 1005, 1011 | confirmado |
| ENT-13 | `m` se separa por `;`. Si algún segmento queda vacío (`;;`, un `;` al final o el control vacío), responde 400 `{"error":"E104","mensaje":"segmento vacío"}`. | 981, 982, 1012, 1027, 1058 (antes 43, 44, 108) | confirmado |
| ENT-14 | Los campos extra del cuerpo se ignoran. El `Content-Type` también se ignora: un JSON válido con `text/plain` se procesa igual. | 975, 1007, 979, 1010 | confirmado |
| ENT-15 | Las respuestas de `/msg` con un token válido traen el header `X-Req`, un contador por token. `__reset` no lo reinicia (853 → 855: 20, 21), pero volvió a 1 con el despliegue de las 15:30 (832: 846 → 834: 1). El evaluador no compara headers y el reemplazo no lo envía. | campo `x_req` de 853–855, 832–834 | probable |

Orden de evaluación de la entrada (las pruebas están en la sección 5):
`ruta (E404) → token (E001) → tamaño (E101) → JSON (E100) → m (E102) → ";" (E103) → segmento vacío (E104) → control`.

## 2. Integridad (`INT`)

Es cómo comprueba el servicio que el mensaje llegó sin alteraciones. Cada mensaje termina con un
número de **control** que se calcula a partir del resto del mensaje, por ejemplo `PING;64`. El
servicio vuelve a calcularlo y, si no coincide, rechaza el mensaje sin ejecutarlo (`E201` si el
control no es un número de 1 o 2 cifras, `E202` si el número no corresponde). Es la primera
validación después de la entrada, así que **un cliente que no sepa calcular el control no puede
usar ningún comando**, salvo `PING`, que no lo revisa.

El control usa el algoritmo ISO 7064 MOD 97-10, el mismo del dígito de control del IBAN:

```
1. Se toma el mensaje sin ";control" y se pasa a mayúsculas.
2. Cada letra A–Z se reemplaza por su posición (A=1 … Z=26, sin ceros a la izquierda) y cada
   dígito queda igual. Todo lo demás (";", "-", ".", espacios, tildes, ñ) se descarta.
3. N = el número que forman esos dígitos concatenados.
4. control = 98 − (100·N mod 97)            → siempre entre 2 y 98
```

Ejemplo: `PING` → `16 9 14 7` → N = 169147 → control 64 → `PING;64`.

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| INT-01 | El control se calcula con la fórmula de arriba. Se verificó 20 de 20 en mensajes nuevos y se repitió después del cambio sin ninguna diferencia. | 854–905, 1032–1046 (antes 456–479) | confirmado |
| INT-02 | Los caracteres que no son A–Z ni dígitos se descartan del cálculo. Se probó con í, é, ú, ñ y espacios en `ALTA`. | 1048–1056 (antes 480–508) | confirmado |
| INT-03 | El control tiene que ser de 1 o 2 cifras. Si no (`014`, `100`, `111`, `999`, `-1`, `+14`, `" 14"`, `"14 "`, `5X`), responde 400 `{"error":"E201","mensaje":"control mal formado"}`. | 850, 1019–1026 (antes 18, 97, 100–107) | confirmado |
| INT-04 | Un control con formato correcto pero con otro valor (incluidos 0, 1, 97 y 98 cuando no corresponden) responde 400 `{"error":"E202","mensaje":"control inválido"}`. | 835, 860, 875–881, 903–905, 1036, 1041 (antes 3, 95) | confirmado |
| INT-05 | El control se valida **antes** que el comando, la aridad y la existencia de la cuenta. | 1014, 1015, 1016, 1017, 880, 881 (antes 95–98) | confirmado |
| INT-06 | `PING` **no valida el control**: `PING;65`, `PING;0` y `PING;XX` responden `pong`. Sí exige el `;` (E103) y que no haya segmentos vacíos (E104). | 1028–1030, 980, 982 (antes 109–111) | confirmado |

## 3. Comandos (`COM`)

Los comandos no distinguen mayúsculas (`CONSULTa`, `alta`). Los IDs de cuenta y de operación sí
(`ac-0001` y `op-0001` no existen).

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| COM-01 | El nombre del comando no distingue mayúsculas. | 844, 1217 (antes 12, 133, 829) | confirmado |
| COM-02 | Los IDs de cuenta (`AC-0001`) y de operación (`OP-0001`) distinguen mayúsculas y tienen que coincidir exactamente: `ac-0001`, `AC-1`, `AC-00001` y `XX-0001` dan E401, y `op-0001` da E402. | 1063–1066, 1125 (antes 540, 737) | confirmado |
| COM-03 | Un comando desconocido responde 400 `{"error":"E301","mensaje":"comando desconocido "}`, **con un espacio al final**. | 845, 868, 869, 898 (antes 13, 142, 143) | confirmado |
| COM-04 | Si un comando conocido (`ALTA`, `ANULA`, `CONSULTA`, `DEPOSITO`, `HALT`, `PING`, `TRANSFER`) está a una distancia de Levenshtein ≤ 2 del comando recibido en mayúsculas, se agrega `"sugerencia":"<COMANDO>"`. Con distancia 3 no se agrega. Los argumentos no influyen. | 899, 1205–1213, 1215, 1219; sin sugerencia 1214, 1216 (antes 817–828) | confirmado |
| COM-05 | Si hay empate en la distancia, la sugerencia es el primero en orden alfabético (`HALTA` → `ALTA`; `HANG` y `PILT` → `HALT`, que va antes que `PING`). | 1220, 1346, 1347 (antes 832) | confirmado |
| COM-06 | Si la cantidad de argumentos no es la del comando, responde 400 `{"error":"E302","mensaje":"aridad inválida"}`. Aridad: `ALTA` 1, `CONSULTA` 1, `DEPOSITO` 2, `TRANSFER` 3, `ANULA` 1, `HALT` 1. | 853, 870–874, 900, 901, 1218, 1309 (antes 21, 144–148) | confirmado |

### `ALTA;nombre`

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| COM-ALTA-01 | Crea una cuenta con saldo 0 y responde **201** `{"cuentaId":"AC-0001"}` (camelCase). Los IDs son correlativos: `AC-0001`, `AC-0002`… | 836, 837, 1405 (antes 4, 5) | confirmado |
| COM-ALTA-02 | Acepta cualquier nombre no vacío: una letra, dígitos, 200 letras, tildes, ñ y espacios. Un nombre vacío da E104. | 1059–1062, 1048–1056, 1058 (antes 500–508, 533–536) | confirmado |
| COM-ALTA-03 | Dos `ALTA` con el mismo nombre en el mismo estado no se probaron. El reemplazo crea una cuenta nueva cada vez. | — | supuesto |

### `CONSULTA;cuenta`

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| COM-CONSULTA-01 | Responde 200 `{"cuenta_id":"AC-0001","saldo":"<saldo>"}` (snake_case). `saldo` es **texto** con el saldo en centavos dividido por 100 y siempre 2 decimales: 0 → `"0.00"`, 40000 → `"400.00"`, 40700 → `"407.00"`. | 838, 841, 852, 1067, 1406 | confirmado |
| COM-CONSULTA-02 | Un saldo negativo (posible después de un `ANULA`) se muestra con signo: `"-400.00"`. | 1121 | probable |
| COM-CONSULTA-03 | Si la cuenta no existe, responde **404** `{"error":"E401","mensaje":"cuenta inexistente"}`. | 848, 966, 1063–1066 (antes 16, 99) | confirmado |
| COM-CONSULTA-04 | Saldos de 9 cifras o más (separador de miles, notación): sin probar. El reemplazo usa el mismo formato, sin separador. | — | supuesto |

### `DEPOSITO;cuenta;monto`

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| COM-DEPOSITO-01 | Suma el monto al saldo y responde 200 `{"status":"recieved","operacionId":"OP-0001"}` (con la falta de ortografía `recieved`). | 839, 851, 942 (antes 7, 19) | confirmado |
| COM-DEPOSITO-02 | El monto tiene que ser un entero de 1 a **9.999.999.999**, sin signo, sin decimales y sin ceros a la izquierda. `0`, `-100`, `10.5`, `abc`, `0700` y `10000000000` dan 400 `{"error":"E303","mensaje":"monto inválido"}`. Un rechazo no cambia el saldo. | 937–944, 1240–1296, 1301–1302 (antes 518–524, 602–606) | confirmado |
| COM-DEPOSITO-03 | El máximo es por depósito, no por saldo: con el saldo en 9.999.999.999 se puede depositar 1 más. | 1301, 1303 (antes 606) | confirmado |
| COM-DEPOSITO-04 | Si la cuenta no existe, responde 404 `E401`. | 865, 884, 886 | confirmado |
| COM-DEPOSITO-05 | Un depósito en una cuenta bloqueada se acepta y además la desbloquea (ver MEM-08). | 1077, 1335, 1356 | confirmado |

### `TRANSFER;origen;destino;monto`

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| COM-TRANSFER-01 | Resta el monto del origen, lo suma al destino y responde 200 `{"status":"recieved","operacionId":"OP-000N"}`. | 840, 922, 959, 1113 (antes 8) | confirmado |
| COM-TRANSFER-02 | El monto se valida igual que en `DEPOSITO` (E303). | 945–948, 1304 (antes 526–529) | confirmado |
| COM-TRANSFER-03 | Límite de **50.000 por operación**: 50.000 se acepta y 50.001 responde **422** `{"error":"E506","mensaje":"límite excedido"}`. No depende del saldo. | 958, 959, 843, 924, 862 | confirmado |
| COM-TRANSFER-04 | Si el monto supera el saldo del origen, responde **422** `{"error":"E507","mensaje":"saldo insuficiente"}`. Se puede transferir exactamente el saldo. | 849, 1100, 1188; 922–923 (antes 17) | confirmado |
| COM-TRANSFER-05 | Si origen y destino son la misma cuenta, responde 400 `{"error":"E304","mensaje":"origen y destino iguales"}`, aunque la cuenta no exista. | 925, 1149, 1185 (antes 700) | confirmado |
| COM-TRANSFER-06 | Si el origen o el destino no existen, responde 404 `E401`. | 927, 928, 866 (antes 702–703) | confirmado |
| COM-TRANSFER-07 | Una cuenta bloqueada no puede transferir. Responde **423** `{"error":"E510","mensaje":"cuenta bloqueada","intentos":N}` (ver MEM-04 a MEM-08). | 1075, 1103, 1199 | confirmado |
| COM-TRANSFER-08 | Un límite acumulado (además del límite por operación) no se pudo aislar, porque montos repetidos de 80.000 ya superan el límite por operación. El reemplazo no tiene límite acumulado. | 912–915 | supuesto |

### `ANULA;operacion`

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| COM-ANULA-01 | Anula un depósito o una transferencia y revierte los saldos. Responde 200 `{"ok":true,"anulada":"OP-0002"}`. | 1110–1111, 1113–1116 (antes 14, 722–727) | confirmado |
| COM-ANULA-02 | Revierte aunque el destino ya haya gastado el dinero, y el destino queda con saldo negativo. | 1117–1121 (antes 729–733) | confirmado |
| COM-ANULA-03 | Anular una operación ya anulada responde **200** (no un error) `{"ok":false,"motivo":"ya anulada"}`. | 1112 (antes 15, 724) | confirmado |
| COM-ANULA-04 | Si la operación no existe (un número que no existe, un ID de cuenta, `xyz`, `op-0001`), responde 404 `{"error":"E402","mensaje":"operación inexistente"}`. | 846, 847, 867, 1122–1125 (antes 734–737) | confirmado |
| COM-ANULA-05 | Una cuenta bloqueada puede anular sus operaciones. | 1135–1136 (antes 747) | confirmado |

### `HALT;argumento`

`HALT` es un **comando oculto**: no aparece en el enunciado ni en los 20 ejemplos oficiales. Lo
descubrimos porque el servicio lo sugería al recibir comandos parecidos (`HOLA` → `"sugerencia":"HALT"`).
Ya existía en la versión 1: allí se sugería (473, 817, 824, 825) y `halt;71` daba `E302` en vez de
`E301`, señal de que lo reconocía como comando (830). Según su propio mensaje, **detiene el
servicio**. En vez de ejecutarse, responde `E520` y pide una confirmación. Esa confirmación no la
probamos a propósito, para no apagar el servicio durante la exploración.

Respuesta con 1 argumento en la versión 1: no se probó. No sabemos si cambió a las 15:30, y por eso
no figura entre los cambios de la sección 6.

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| COM-HALT-01 | Con 1 argumento cualquiera (el argumento no se valida como cuenta) responde **409** `{"error":"E520","mensaje":"operación destructiva: detiene el servicio; reenvía con confirmación"}`. | 1310, 1311, 1407 | confirmado |
| COM-HALT-02 | El `E520` no cambia nada: después siguen funcionando `CONSULTA`, `DEPOSITO`, `TRANSFER`, `ALTA`, `PING` y `/health`. | 1312–1319, 1408–1409 | confirmado |
| COM-HALT-03 | Sin argumentos o con 4 da E302. | 1218, 1309 (antes 830) | confirmado |
| COM-HALT-04 | Cómo se confirma `HALT` no se probó a propósito, porque dice que detiene el servicio. El reemplazo responde `E520` a todo `HALT` de 1 argumento, y con 2 o 3 argumentos da E302. | — | supuesto |
| COM-HALT-05 | `HALT` es un comando oculto (no aparece en el enunciado ni en los ejemplos), pero el servicio lo reconoce en las dos versiones: lo sugiere ante comandos parecidos (`HOLA` → `HALT`) y, con la aridad incorrecta, da E302 en vez de E301. | 899, 1205, 1218 (antes 473, 817, 830) | confirmado |

### `PING;control`

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| COM-PING-01 | Responde 200 `{"pong":true}` y no cambia el estado. No valida el control (INT-06). | 834, 967, 1028–1030, 1403 (antes 2, 109–111) | confirmado |
| COM-PING-02 | `PING` con argumentos además del control no se probó. El reemplazo responde `pong`. | — | supuesto |

## 4. Memoria entre requests (`MEM`)

El estado vive en memoria y es propio de cada token: cuentas, saldos, operaciones (con su marca de
anulada) y, por cada cuenta, un contador de rechazos, la marca de bloqueo y el contador `intentos`.
`POST /__reset` lo borra todo.

| ID | Comportamiento | Evidencia | Confianza |
| --- | --- | --- | --- |
| MEM-01 | Las cuentas se numeran `AC-0001`, `AC-0002`… en orden de creación (4 dígitos). Un `ALTA` rechazado no consume número. | 835–837 (antes 3–5) | confirmado |
| MEM-02 | Depósitos y transferencias comparten una sola numeración `OP-0001`, `OP-0002`… Los rechazos no consumen número, y `ANULA` tampoco. | 1072–1077 (rechazos, después `OP-0002`); 846–851 (`ANULA` fallidos, después `OP-0003`); 1110 → 1113 (`ANULA` exitoso, después `OP-0003`) | confirmado |
| MEM-03 | Los saldos se acumulan entre requests y `__reset` los borra. | 838–852, 966, 1405–1406 | confirmado |
| MEM-04 | **Bloqueo**: cada cuenta lleva un contador de rechazos `E506`/`E507` seguidos como origen de `TRANSFER`. Al llegar a **3** la cuenta queda bloqueada: 3 × E506, 3 × E507 o una mezcla de los dos. | 1072–1075, 1100–1103, 1131–1134 (antes 623–626, 712–715) | confirmado |
| MEM-05 | Con 2 rechazos la cuenta todavía no está bloqueada, y una transferencia exitosa reinicia el contador. | 1086–1090 (antes 647–649) | confirmado |
| MEM-06 | `E303`, `E304` y `E401` no suman al contador **ni lo reinician**: con 3 seguidos no se bloquea, y si quedan entre dos E506 no cortan la racha. | 1145–1156; 1165–1179 (antes 757–791) | confirmado |
| MEM-07 | Una cuenta bloqueada puede consultar, recibir depósitos y transferencias y anular sus operaciones. Las demás cuentas no se ven afectadas. | 1076–1081, 1334, 1135, 1341 | confirmado |
| MEM-08 | **`intentos`**: cada `E510` de la cuenta suma 1 (el primero es 1) y no tiene tope (llegó a 7). Es por cuenta. Los `E303`, `E304` y `E401` en una cuenta bloqueada no lo suben. | 1328–1333, 1376–1382, 1341, 1330–1331, 1200–1202 | confirmado |
| MEM-09 | **Desbloqueo**: un `DEPOSITO` en la propia cuenta bloqueada la desbloquea y reinicia los dos contadores. Si después se vuelve a bloquear, `intentos` empieza otra vez en 1. | 1355–1357, 1335–1336, 1395–1401 | confirmado |
| MEM-10 | No desbloquean: una `CONSULTA`, un depósito en otra cuenta ni una transferencia entrante. | 1367–1368, 1391–1392, 1393–1394 | confirmado |
| MEM-11 | Un depósito en una cuenta **no** bloqueada que ya tiene 1 o 2 rechazos: no se probó si reinicia el contador. El reemplazo no lo reinicia. | — | supuesto |

## 5. Errores (`ERR`)

### Catálogo

Todos los errores tienen el cuerpo `{"error":"<código>","mensaje":"<mensaje>"}`, salvo E301 y E510,
que pueden agregar un campo.

| ID | Status | Cuerpo exacto | Evidencia | Confianza |
| --- | --- | --- | --- | --- |
| ERR-E001 | 401 | `{"error":"E001","mensaje":"no autorizado"}` | 961, 993 | confirmado |
| ERR-E404 | 404 | `{"error":"E404","mensaje":"ruta desconocida"}` | 984, 1000 | confirmado |
| ERR-E101 | 413 | `{"error":"E101","mensaje":"cuerpo demasiado grande"}` | 989, 1237 | confirmado |
| ERR-E100 | 400 | `{"error":"E100","mensaje":"json inválido"}` | 970, 1003 | confirmado |
| ERR-E102 | 400 | `{"error":"E102","mensaje":"falta m"}` | 971, 1004 | confirmado |
| ERR-E103 | 400 | `{"error":"E103","mensaje":"falta control"}` | 972, 1011 | confirmado |
| ERR-E104 | 400 | `{"error":"E104","mensaje":"segmento vacío"}` | 981, 1012 | confirmado |
| ERR-E201 | 400 | `{"error":"E201","mensaje":"control mal formado"}` | 850, 1019 | confirmado |
| ERR-E202 | 400 | `{"error":"E202","mensaje":"control inválido"}` | 835, 1014 | confirmado |
| ERR-E301 | 400 | `{"error":"E301","mensaje":"comando desconocido "}` (espacio final), con `"sugerencia":"<COMANDO>"` opcional | 845, 1206 | confirmado |
| ERR-E302 | 400 | `{"error":"E302","mensaje":"aridad inválida"}` | 853, 870 | confirmado |
| ERR-E303 | 400 | `{"error":"E303","mensaje":"monto inválido"}` | 937, 945 | confirmado |
| ERR-E304 | 400 | `{"error":"E304","mensaje":"origen y destino iguales"}` | 925, 1149 | confirmado |
| ERR-E401 | 404 | `{"error":"E401","mensaje":"cuenta inexistente"}` | 848, 927 | confirmado |
| ERR-E402 | 404 | `{"error":"E402","mensaje":"operación inexistente"}` | 846, 1122 | confirmado |
| ERR-E506 | 422 | `{"error":"E506","mensaje":"límite excedido"}` | 843, 958 | confirmado |
| ERR-E507 | 422 | `{"error":"E507","mensaje":"saldo insuficiente"}` | 849, 1100 | confirmado |
| ERR-E510 | 423 | `{"error":"E510","mensaje":"cuenta bloqueada","intentos":N}` | 1075, 1199 | confirmado |
| ERR-E520 | 409 | `{"error":"E520","mensaje":"operación destructiva: detiene el servicio; reenvía con confirmación"}` | 1310, 1407 | confirmado |
| ERR-ANULA | 200 | `{"ok":false,"motivo":"ya anulada"}`: un fallo que se responde con status 200 | 1112 | confirmado |

### Orden de evaluación

```
Entrada:   ruta E404 → token E001 → tamaño E101 → JSON E100 → m E102 → ";" E103 → segmento vacío E104
Control:   (PING sale aquí con pong) → formato E201 → valor E202
Comando:   desconocido E301 → aridad E302
DEPOSITO:  monto E303 → cuenta E401
TRANSFER:  monto E303 → misma cuenta E304 → cuenta E401 → bloqueada E510 → límite E506 → saldo E507
```

| ID | Comportamiento (gana el primero) | Evidencia | Confianza |
| --- | --- | --- | --- |
| ERR-ORDEN-01 | E404 antes que E001 | 987, 1002 (antes 49, 64) | confirmado |
| ERR-ORDEN-02 | E101 antes que E103 (un cuerpo grande sin `;`) | 1237, 1224 (antes 91) | confirmado |
| ERR-ORDEN-03 | E104 antes que E202 (`CONSULTA;;14`) | 1012 | probable |
| ERR-ORDEN-04 | E201/E202 antes que E301, E302 y E401 | 1014–1017, 880, 881 (antes 95–98) | confirmado |
| ERR-ORDEN-05 | E301 antes que E302 (un comando desconocido con cualquier cantidad de argumentos da E301) | 869, 1219 | confirmado |
| ERR-ORDEN-06 | `DEPOSITO`: E303 antes que E401 | 1344, 1345 | confirmado |
| ERR-ORDEN-07 | `TRANSFER`: E303 antes que E304, E401 y E510 | 1184, 932, 1200 | confirmado |
| ERR-ORDEN-08 | `TRANSFER`: E304 antes que E401, E506, E507 y E510 | 1185, 1186, 1187, 1191, 1330 | confirmado |
| ERR-ORDEN-09 | `TRANSFER`: E401 antes que E506, E507 y E510 | 930, 931, 1201 | confirmado |
| ERR-ORDEN-10 | `TRANSFER`: E510 antes que E506 y E507 | 1202, 1203 | confirmado |
| ERR-ORDEN-11 | `TRANSFER`: E506 antes que E507 (sobre el límite y sin saldo da E506) | 924, 929, 1132 | confirmado |

## 6. Cambios durante el día (`CAM`)

**Qué pasó.** A las **15:30** el proveedor desplegó la **versión 2** del servicio sin avisar (ticket
FR-0153). Cambiaron **3 comportamientos** y el resto quedó igual.

**Cómo lo detectamos.** Antes de dar la exploración por cerrada repetimos la **línea base** (los 20
ejemplos oficiales, secuencia `F0-linea-base`) a las 18:19 (833–853) y la comparamos con la de las
13:26 (1–21) usando `explorador diferencias 15:30`, que compara solo el log. 8 de las 20 respuestas
fueron distintas. Después repetimos todas las fases de la exploración en la versión 2 (854–1304)
para aislar cada cambio con el mismo request antes y después. Las 8 diferencias de la línea base
se explican con los 3 cambios: la transferencia de 100.000 que ahora se rechaza (843) cambia el
saldo siguiente (844) y corre la numeración de operaciones (846, 847, 851, 852).

**Desde cuándo.** Entre el último request de la versión 1 (#832, 15:22:32) y el primero de la
versión 2 (#833, 18:19:21) no se envió nada, así que ninguna línea mezcla las dos versiones. El
contador `X-Req` volvió a 1 en #834 (antes iba en 846), señal de que el servicio se reinició
(ENT-15). La hora exacta, 15:30, viene del ticket.

| ID | Qué cambió | Versión 1 (antes de las 15:30) | Versión 2 (desde las 15:30) | Evidencia (antes → después) | Confianza |
| --- | --- | --- | --- | --- | --- |
| CAM-01 | Formato del saldo en `CONSULTA` | Número entero: `"saldo":40000`, `"saldo":-40000` | Texto con 2 decimales, el monto en centavos: `"saldo":"400.00"`, `"-400.00"`, `"0.00"` | 9 → 841 (el mismo request); 6 → 838; 523 → 942; 733 → 1121 | confirmado |
| CAM-02 | Límite de `TRANSFER` por operación | 100.000 (100.000 se aceptaba, 100.001 daba E506) | **50.000** (50.000 se acepta, 50.001 da E506) | 11 → 843 (el mismo request: antes 200, ahora E506); 136 → 862 y 699 → 924 (antes E507, ahora E506); borde 958/959 | confirmado |
| CAM-03 | Error de cuenta bloqueada `E510` | **409** `{"error":"E510","mensaje":"cuenta bloqueada"}` | **423** `{"error":"E510","mensaje":"cuenta bloqueada","intentos":N}` | 634 → 1075 (el mismo request); 811 → 1199, 814 → 1202, 815 → 1203 | confirmado |
| CAM-04 | Sin cambios | Entrada, rutas y autenticación, tamaño máximo, fórmula del control, validación y máximo de montos, numeración, regla de bloqueo (3 rechazos), `ANULA`, orden de errores y sugerencias | Igual | Fases repetidas: 854–905 (control), 960–1030 (entrada), 1031–1304 (comandos y memoria) | confirmado |

**Qué implica cada cambio**

- **CAM-01, saldo.** Solo cambió cómo se **muestra** el saldo: los montos siguen entrando como
  enteros en centavos (`DEPOSITO;AC-0001;250000` → `"2500.00"`, 936 y 942). Un cliente de la
  versión 1 que leía `saldo` como número ahora recibe un string, y ve un valor 100 veces menor si
  lo convierte sin dividir.
- **CAM-02, límite.** Además del límite nuevo, cambia **qué error se ve**. El límite se revisa
  antes que el saldo (ERR-ORDEN-11), así que un monto entre 50.001 y el saldo disponible, que antes
  daba E507, ahora da E506 (862, 924). Como E506 suma al contador de bloqueo (MEM-04), con el mismo
  tráfico las cuentas se bloquean antes.
- **CAM-03, cuenta bloqueada.** El status pasa de 409 (conflicto) a 423 (recurso bloqueado), que
  describe mejor el caso. `intentos` le dice al cliente cuántas veces intentó transferir desde la
  cuenta bloqueada. Sus reglas (qué lo sube y qué lo reinicia) están en MEM-08 y MEM-09.

**Cómo lo resolvimos.** El reemplazo implementa solo la versión 2. Los tres cambios viven en un
lugar cada uno: el formato del saldo en `_formato_saldo`, el límite en `LIMITE_TRANSFERENCIA` y el
status de E510 en `respuestas.py`, junto con el contador `Cuenta.intentos`. `api/tests/test_log.py` reproduce contra el
reemplazo todas las secuencias del log posteriores al cambio y compara status y cuerpo con los del
original: 454 tests en verde.

**Qué haríamos distinto.** Detectamos el cambio casi 3 horas tarde, porque entre las 15:22 y las
18:19 no mandamos requests. Repetir la línea base cuesta 21 requests (de 8.000 por día). Correrla
cada 30 minutos habría detectado el cambio a tiempo.

En `experimentos.jsonl`, la `conclusion` de cada línea clave del cambio empieza con
`CAMBIO 15:30 [CAM-0N]` y cita la línea equivalente de la versión 1 (838, 841, 844, 852, 942, 1121,
843, 862, 924, 958, 959, 1075, 1199, 1202, 1203).

Lo que solo se probó en la versión 2, sin comparación con la versión 1: el desbloqueo por depósito
(MEM-09), `E520` (COM-HALT-01) y el tope de `intentos` (MEM-08).

## 7. Riesgos (`RIE`)

Son comportamientos que el reemplazo copia porque el contrato lo exige, pero que un cliente nuevo no
debería heredar.

| ID | Comportamiento | Evidencia | Cómo lo cerraríamos |
| --- | --- | --- | --- |
| RIE-01 | `ANULA` revierte una transferencia aunque el destino ya gastó el dinero, y su saldo queda negativo. | 1117–1121 | Rechazar la anulación si el destino no tiene saldo suficiente, con un error propio (409). |
| RIE-02 | Los fallos de `ANULA` ("ya anulada") responden 200, así que un cliente que mira solo el status cree que funcionó. | 1112 | Responder 409 con un código de error, como los demás fallos. |
| RIE-03 | `HALT` es un comando destructivo al alcance de cualquier token, y el `E520` explica cómo confirmarlo. | 1310, 1407 | Quitarlo de la API pública o exigir un rol de administrador. |
| RIE-04 | La sugerencia de E301 revela comandos ocultos (`HOLA` → `HALT`). | 899, 1205 | No sugerir comandos administrativos, o quitar la sugerencia. |
| RIE-05 | Un depósito de cualquier monto desbloquea una cuenta bloqueada, y cualquiera con el token puede depositar en cualquier cuenta. El bloqueo no protege. | 1355–1357 | Desbloquear solo con una acción explícita o después de un tiempo. |
| RIE-06 | No hay autorización por cuenta: con el token se puede transferir desde cualquier cuenta. | 840, 1113 | Asociar las cuentas a su dueño y validar el origen. |
| RIE-07 | `PING` no valida el control, a diferencia del resto de los comandos. | 1028–1030 | Validarlo igual que los demás. |
| RIE-08 | El servicio cambió el tipo de `saldo` (de número a texto), el límite y el status de E510 sin versionar la API ni avisar. Los clientes que leían `saldo` como número o esperaban 409 se rompen en silencio. | CAM-01 a CAM-03 | Versionar la API (`/v2/msg`) y anunciar los cambios de contrato. |
| RIE-09 | Los montos de entrada son enteros en centavos, pero el saldo se muestra en unidades con decimales: un cliente puede depositar 400 creyendo que son 400,00. | 839 → 841 | Usar la misma unidad en la entrada y en la salida, o documentarla en cada campo. |
| RIE-10 | Defectos del contrato: `"recieved"`, el espacio final en `"comando desconocido "` y `cuentaId` frente a `cuenta_id`. | 839, 845, 836 / 838 | Corregirlos en una versión nueva. El reemplazo los copia tal cual. |
