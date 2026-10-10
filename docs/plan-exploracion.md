# Reto 2 · La caja negra — Plan de exploración

> **Estado:** borrador. Cubre cómo estudiar el sistema antiguo. Validar el reemplazo contra el
> original (comparador diferencial) queda para la etapa siguiente, cuando el reemplazo exista.

## 1. Objetivo

Entender cómo responde el sistema antiguo a distintos valores, registrando qué se le manda y qué
responde. Cada respuesta registrada es la respuesta que el reemplazo tiene que dar ante la misma
secuencia tras un reset.

## 2. Alcance

- Las secuencias del set de evaluación tienen como mucho 12 requests. No exploramos desbordes de
  contadores (`AC-9999`), límites diarios ni comportamientos que necesiten cientos de operaciones.
  Si aparece algo así, el reemplazo usa un comportamiento por defecto y lo anotamos como
  **supuesto** en la especificación.
- No probamos variantes del formato del header `Authorization`, como mayúsculas en `Bearer`. El
  reemplazo usa un comportamiento por defecto y lo anotamos como **supuesto**.
- Sí probamos la forma del cuerpo (JSON mal escrito, cuerpo sin `m`, etc.). La especificación la
  pide en la sección Entrada y cuesta pocos requests.
- El esfuerzo va a la lógica de negocio: el control, los comandos, el orden de los errores y la
  memoria entre requests.

## 3. Kit de exploración

| Componente | Qué hace | ¿Llama al sistema antiguo? |
| --- | --- | --- |
| **Registrador** | Todo request al sistema antiguo pasa por aquí. Guarda en `experimentos.jsonl` la hipótesis, `seq`, `x_req`, `ts` (fecha y hora), status y cuerpo crudo. Detecta `X-Frontier-Infra: rate-limit` y marca esa respuesta como de infraestructura, no del servicio | Sí |
| **Runner de secuencias** | Llama a `/__reset` y manda una lista de requests con una misma `seq` | Sí, a través del registrador |
| **Buscador de control** | Para un mensaje nuevo prueba controles de 0 a 99 hasta encontrar el que no da `E202`. Guarda el resultado en caché | Sí, a través del registrador |
| **Deductor de fórmula** | Toma los pares mensaje → control y deduce la fórmula del control fuera de línea | No, solo analiza datos |

Cada prueba es una secuencia independiente:

```
reset → setup (estado que la prueba necesita) → prueba → CONSULTA de verificación (si aplica)
```

La hipótesis de cada request es una **predicción concreta**: el status y el cuerpo exacto que
esperamos según lo que sabemos hasta ese momento. Empieza con el ID de la regla que prueba, con el
prefijo de su sección en la especificación: `ENT`, `INT`, `COM`, `MEM`, `ERR`, `CAM` o `RIE`
(ej.: `[COM-ANULA-02] Anular un depósito devuelve...`). Ver la sección 5.1 de `planning.md`.

Cada regla de negocio se prueba en **al menos dos secuencias distintas**, con distinta
preparación. Con una sola queda como **probable**. Con dos o más que coinciden queda como
**confirmada**, que es lo que exige la especificación.

## 4. Fases

### Fase 0 · Línea base

Se mandan los 20 requests de `pruebas/ejemplos.jsonl` en orden, tras un reset, a través del
registrador. Son 21 requests.

- Lo que muestran los ejemplos pasa a tener un `id` del log, que es lo que la especificación puede
  citar.
- Si alguna respuesta difiere de la grabada en la mañana, el servicio ya cambió. Se anota con su
  `ts` en la sección Cambios durante el día.

### Fase 1 · Entrada (controlador y rutas)

No necesita el control. Son unos 25 requests.

**Caso principal (token válido)**

| ID | Request | Qué buscamos |
| --- | --- | --- |
| R1 | `POST /msg` con `PING;64` | La respuesta base de un mensaje bien formado en la versión actual |
| R2 | `GET /health` | Status y cuerpo exactos |
| R3 | `POST /__reset` | Status y cuerpo exactos |
| R4 | `POST /__reset` → `CONSULTA;AC-0001;14` | Que el reset deja el estado vacío (se espera E401) |

**Autenticación**

| ID | Request | Qué buscamos |
| --- | --- | --- |
| R5 | `POST /msg` sin token | El error exacto |
| R6 | `POST /msg` con token inválido | El error exacto |
| R7 | `GET /health` sin token | Si `/health` es pública |
| R8 | `POST /__reset` sin token | Si `/__reset` exige token |

**Rutas y métodos desconocidos**

| ID | Request | Qué buscamos |
| --- | --- | --- |
| R9 | `GET /xyz` con token válido | Respuesta a una ruta desconocida |
| R10 | `POST /xyz` con token válido | Si esa respuesta depende del método |
| R11 | `PUT /msg` con token válido | Método desconocido en una ruta que existe (¿404 o 405?) |
| R12 | `GET /xyz` sin token | Si se evalúa primero la autenticación o la ruta |

**Forma del cuerpo** (todos a `POST /msg` con token válido)

| ID | Cuerpo | Qué buscamos |
| --- | --- | --- |
| R13 | `{"m": "PING;64"` (JSON mal escrito) | Error ante JSON inválido |
| R14 | `{}` | Error ante cuerpo sin `m` |
| R15 | `{"m": ""}` | Error ante `m` vacío |
| R16 | `{"m": 123}` y `{"m": null}` | Error ante `m` que no es texto |
| R17 | `{"m": "PING;64", "x": 1}` | Si ignora campos extra |
| R18 | `["PING;64"]` y `"PING;64"` | Error ante un cuerpo que no es objeto |
| R19 | Sin cuerpo y con `Content-Type: text/plain` | Si exige JSON |
| R20 | `m` de 10.000 caracteres | Si hay un límite de tamaño y qué error da |
| R21 | `{"m": "PING"}` (sin control) | Si un mensaje sin control da E201 u otro error |
| R22 | `{"m": ";;;"}` y `{"m": "PING;64;"}` | Campos vacíos y `;` al final |

### Fase 2 · El control

Va antes que el resto porque todas las pruebas de negocio necesitan mensajes con su control válido.
Cuando el deductor encuentra la fórmula, los controles se calculan sin gastar requests y el buscador
queda solo para confirmar predicciones.

| ID | Prueba | Qué aprendemos |
| --- | --- | --- |
| C1 | `CONSULTA;AC-0009;88` | Si el control se valida antes que la cuenta (E202 en vez de E401). Si es así, el buscador funciona sin modificar el estado: con el estado vacío cada intento da E401 o E202 |
| C2 | `SALDOS;AC-0001;<c≠38>` | Si el comando desconocido (E301) se evalúa antes que el control |
| C3 | `ALTA;Lucia;Gomez;<c≠11>` | Si la aridad (E302) se evalúa antes que el control |
| C4 | Controles `100`, `999`, `-1`, `014`, `+14`, `" 14"` y vacío sobre un mensaje de control conocido | Rango y formato aceptados, y dónde se pasa de E201 a E202 |
| C5 | `PING` con otros controles | Si `PING` valida el control |
| C6 | `CONSULTA;AC-000k` con k de 0 a 9 | Cuánto aporta un dígito según su valor |
| C7 | `ALTA;A`, `ALTA;B`, `ALTA;AA`, `ALTA;AB`, `ALTA;BA` | Si importa la posición de cada carácter y la longitud |
| C8 | `consulta;ac-0001`, `ALTA;Lucía` | Si las mayúsculas y los caracteres no ASCII cambian el control |

### Fase 3 · Comandos

**ALTA**

| ID | Setup → prueba | Pregunta |
| --- | --- | --- |
| A1 | `ALTA;;c` | ¿Acepta un nombre vacío? |
| A2 | Nombres con números, espacios, tildes o 200 caracteres | ¿Valida el nombre? |
| A3 | ALTA con control malo → ALTA válido | ¿Un rechazo consume un número de cuenta? |

**CONSULTA**

| ID | Setup → prueba | Pregunta |
| --- | --- | --- |
| Q1 | `AC-1`, `AC-00001`, `ac-0001`, `XX-0001` | ¿El formato del ID da E401 u otro error? |
| Q2 | ALTA → CONSULTA de la cuenta nueva | ¿Una cuenta nueva tiene saldo 0? |

**DEPOSITO**

| ID | Setup → prueba | Pregunta |
| --- | --- | --- |
| D1 | ALTA → montos `0`, `-100`, `10.5`, `abc`, `0700` | ¿Qué montos acepta y qué error da cada uno? |
| D2 | ALTA → monto enorme (`999999999999`) | ¿Hay un límite de depósito? ¿Aplica E506? |
| D3 | Sin ALTA → DEPOSITO | Confirmar E401 |
| D4 | ALTA → dos depósitos → CONSULTA | ¿Los depósitos se suman? |

**TRANSFER**

| ID | Setup → prueba | Pregunta |
| --- | --- | --- |
| T1 | 2 ALTA + depósito grande → montos entre 100000 y 120000 por bisección | ¿Cuál es el límite exacto? (unas 15 secuencias) |
| T2 | Igual → dos transferencias de 80000 | ¿El límite es por operación o se acumula? |
| T3 | Igual → transferencias desde orígenes distintos | Si se acumula, ¿por cuenta o en total? |
| T4 | Transferir exactamente el saldo, y luego el saldo + 1 | ¿Dónde está el borde del saldo? |
| T5 | Transferir a la misma cuenta | ¿Lo permite? ¿Qué error da? |
| T6 | Origen inexistente, destino inexistente, ambos inexistentes | E401 en cada caso y cuál se evalúa primero |
| T7 | Montos `0`, negativo y decimal | Igual que D1 |
| T8 | Monto sobre el límite **y** sobre el saldo | ¿E506 o E507 primero? |
| T9 | Origen inexistente y monto sobre el límite | ¿E401 o E506 primero? |

**ANULA**

| ID | Setup → prueba | Pregunta |
| --- | --- | --- |
| N1 | Depósito → ANULA → CONSULTA | ¿Se puede anular un depósito? |
| N2 | Transferencia → ANULA → CONSULTA de las dos cuentas | ¿Revierte origen y destino? |
| N3 | Transferencia → el destino transfiere ese dinero a otra cuenta → ANULA | ¿Deja saldo negativo, da error o qué responde? |
| N4 | `ANULA;OP-0099`, `ANULA;AC-0001`, `ANULA;xyz` | Respuesta ante una operación inexistente o un ID mal formado |
| N5 | ANULA → nuevo depósito | ¿ANULA consume un número de operación? |
| N6 | 2 transferencias que llegan al límite acumulado → ANULA una → transferir otra vez | ¿Anular libera el límite? (solo si T2 muestra que se acumula) |

### Fase 4 · Contadores y memoria

| ID | Prueba | Pregunta |
| --- | --- | --- |
| M1 | Operaciones rechazadas por cada error (E202, E401, E506, E507) → depósito | ¿Qué rechazos consumen un número `OP`? |
| M2 | ANULA con `ok:false` → depósito | ¿Consume un número? |
| M3 | Secuencias anteriores en otro orden | ¿Hay efectos que dependan del orden? |

### Fase 5 · Repetición para detectar cambios

Cada 1–2 horas el runner repite los 20 de `pruebas/ejemplos.jsonl` y unas 10 secuencias clave de
las fases 2 a 4. Si alguna respuesta cambia, se vuelve a correr ese grupo de pruebas y el cambio se
anota en la sección 6 de la especificación.

## 5. Presupuesto

Cada token admite 10 requests por segundo y 8.000 por día.

| Fase | Requests estimados | Reparto |
| --- | --- | --- |
| 0 | 21 | Un token |
| 1 | ~25 | Un token |
| 2, mientras se busca la fórmula | 1.500–3.000 (30 a 60 mensajes por el buscador) | Dos tokens |
| 3 y 4, con la fórmula resuelta | ~800 (unas 200 secuencias de 3 a 5 requests, contando que cada regla se prueba dos veces) | Resto del equipo |
| 5 | ~300 por día | Un token |

## 6. Criterio de cierre

Sin el reemplazo, la coincidencia se mide con **predicciones**:

1. Se arma un lote de unas 30 secuencias que nunca se mandaron al sistema antiguo, con la forma del
   set de evaluación (de un request, de 2 a 5 y de 6 a 12).
2. Antes de mandar cada request se escribe la respuesta esperada: status y cuerpo exacto.
3. El scraper compara la respuesta real con la predicción, con las reglas del evaluador: mismo
   status; si los dos cuerpos son JSON, claves en cualquier orden y arrays en el mismo orden; si
   alguno no es JSON, texto exacto.

| Criterio | Umbral |
| --- | --- |
| Predicciones acertadas en un lote nuevo | **≥ 80 %** (umbral inicial, se puede afinar) |
| La fórmula del control acierta en mensajes nuevos | **20 de 20** |
| Cada comando y cada error del plan tiene al menos una prueba en el log | 100 % |
| Cada regla de negocio que usa el reemplazo se repite en al menos dos secuencias (confirmada) | 100 %; el resto queda como probable o supuesto |

La fórmula del control exige el 100 % porque un fallo hace que el reemplazo responda `E202` donde el
original aceptaba el mensaje, y la secuencia entera falla.

Si una ronda queda por debajo del umbral, cada predicción fallada pasa a ser una hipótesis de la
ronda siguiente, que se mide con un lote nuevo.
