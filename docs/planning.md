# Reto 2 · La caja negra — Documento de diseño

## 1. El problema

Hay un servicio antiguo que recibe mensajes por HTTP y nadie sabe qué hace por dentro. Tenemos que
construir un reemplazo que responda **exactamente igual**: el mismo código de respuesta y el mismo
contenido, errores incluidos. Solo podemos estudiarlo desde fuera, mandándole mensajes y mirando qué
responde.

### Lo que ya sabemos

A partir de los 20 ejemplos que nos dieron:

- Es un **sistema bancario simple**. Se abren cuentas (`ALTA`), se consulta el saldo (`CONSULTA`),
  se deposita (`DEPOSITO`), se transfiere (`TRANSFER`) y se anulan operaciones (`ANULA`). Además
  hay un `PING` para comprobar que responde.
- Los mensajes tienen la forma `COMANDO;dato1;dato2;...;control`. Ejemplo:
  `DEPOSITO;AC-0001;250000;86`.
- **El último número es un control**, parecido al dígito verificador de una cuenta bancaria. Se
  calcula a partir del resto del mensaje. Si no coincide, el servicio rechaza el mensaje con
  `E202 control inválido`. Por eso, al cambiar el monto de un ejemplo, el mensaje deja de
  funcionar.
- **El servicio tiene memoria.** Las cuentas se numeran `AC-0001`, `AC-0002`… y las operaciones
  `OP-0001`, `OP-0002`…; los saldos se acumulan y una anulación devuelve el dinero.
- **Tiene reglas de negocio con errores propios.** Ejemplos: cuenta inexistente, saldo
  insuficiente, límite de transferencia excedido (entre 100.000 y 120.000), comando desconocido o
  número de datos incorrecto.
- **Tiene defectos que hay que copiar tal cual**, porque la comparación es letra por letra:
  `"recieved"` mal escrito, un espacio sobrante al final de `"comando desconocido "`, y nombres
  distintos para el mismo dato (`cuentaId` y `cuenta_id`).

### Lo difícil

1. **La fórmula del control.** Probamos más de 20 fórmulas conocidas y ninguna encaja. Sin ella no
   podemos mandar mensajes nuevos al servicio, y el reemplazo no sabría cuáles rechazar.
2. **El orden de los errores.** Cuando un mensaje tiene dos problemas a la vez, hay que saber cuál
   reporta primero el servicio.
3. **Reglas con más de una explicación.** Ejemplo: el límite de transferencia puede ser por
   operación o acumulado. Los ejemplos encajan con las dos.
4. **El servicio puede cambiar durante el día** y dejar obsoleto lo que aprendimos.

## 2. Supuestos y lo que dejamos fuera

| Tema | Decisión | Por qué |
| --- | --- | --- |
| Casos que no podemos probar | El reemplazo usa un comportamiento por defecto y lo anotamos como **supuesto** | Inventar reglas sin evidencia arriesga respuestas falsas, y una afirmación falsa resta puntos |
| Errores que nunca vimos | No los inventamos | Sin haberlos visto no podemos copiar su texto exacto |
| Situaciones que necesitan cientos de operaciones (ej.: la cuenta `AC-9999`) | Fuera de alcance | Las pruebas tienen como mucho 12 mensajes |
| Variantes del formato del header de autenticación (ej.: `bearer` en minúsculas) | Comportamiento por defecto, anotado como supuesto | Aportan poco frente a la lógica de negocio |
| Defectos del original | Se copian, no se corrigen | El objetivo es responder igual. Se documentan como riesgos en la especificación |

## 3. La solución en tres piezas

```
1. EXPLORAR  →  2. CONSTRUIR  →  3. MEDIR
   el servicio     el reemplazo     que responden igual
   antiguo
```

1. **Explorar:** mandamos mensajes al servicio antiguo de forma automatizada y registramos cada uno
   con lo que esperábamos y lo que respondió. Es la parte más compleja y la que decide el
   resultado.
2. **Construir:** primero un esqueleto con las rutas básicas, desplegado pronto. Las reglas de
   negocio se agregan a medida que la exploración las confirma.
3. **Medir:** antes de construir comparamos nuestras predicciones con el servicio real; después
   comparamos el reemplazo con todo lo registrado.

## 4. Plan de exploración

### 4.1 Herramientas

| Herramienta | Qué hace |
| --- | --- |
| **Registrador** | Todo mensaje al servicio antiguo pasa por aquí. Lo anota en `experimentos.jsonl` (ver sección 5). Nunca usamos pruebas manuales: lo que no queda registrado no sirve como evidencia |
| **Ejecutor de secuencias** | Limpia el estado (`/__reset`) y manda una lista de mensajes en orden |
| **Buscador de control** | Para un mensaje nuevo prueba controles del 0 al 99 hasta dar con el que el servicio acepta. Sirve mientras no conozcamos la fórmula |
| **Deductor de fórmula** | Analiza los pares mensaje → control encontrados para descubrir la fórmula. No llama al servicio |

### 4.2 Cómo es cada prueba

```
limpiar estado → preparar (ej.: abrir cuentas) → probar → consultar el saldo para verificar
```

Antes de mandar cada mensaje escribimos **qué esperamos que responda**: el código y el contenido
exactos. Si fallamos, aprendemos algo y la regla se corrige.

Si acertamos una vez, la regla queda como **probable**. Pasa a **confirmada** cuando se repite en
al menos **dos secuencias distintas**, que es lo que exige la especificación ("lo probaste y se
repite"). Por eso cada regla importante se prueba al menos dos veces, en secuencias con distinta
preparación. Las repeticiones de la vigilancia (fase 5) también cuentan.

### 4.3 Fases

| Fase | Objetivo | Ejemplos de pruebas | Mensajes |
| --- | --- | --- | --- |
| **0. Línea base** | Volver a mandar los 20 ejemplos con el registrador. Así lo que muestran tiene un `id` del log que la especificación puede citar, y sabemos si el servicio ya cambió desde la mañana | Los 20 de `pruebas/ejemplos.jsonl`, en orden, tras un reset | 21 |
| **1. Entrada** | Cómo responde a lo básico: salud, reset, sin token, token inválido, rutas que no existen, y la **forma del cuerpo** | `GET /health` sin token; `GET /xyz`; JSON mal escrito; cuerpo sin `m`; `m` vacío; `m` que no es texto; cuerpo muy grande | ~25 |
| **2. Control** | Descubrir la fórmula del control. Va antes que el resto porque todas las demás pruebas la necesitan | Cambiar un solo dígito o letra y ver cómo cambia el control; ver si importan mayúsculas, tildes y posición | 1.500–3.000 |
| **3. Comandos** | Las reglas de cada comando y sus bordes, cada una en al menos dos secuencias | Montos 0, negativos y decimales; límite exacto de transferencia; anular un depósito; transferir a la misma cuenta | ~800 |
| **3b. Orden de errores** | Qué error gana cuando hay dos problemas a la vez | Monto sobre el límite **y** sin saldo; cuenta inexistente **y** control erróneo | incluido arriba |
| **4. Memoria** | Qué recuerda el servicio y qué consume números de cuenta u operación | ¿Una operación rechazada gasta un número `OP`? ¿Anular libera el límite? | incluido arriba |
| **5. Vigilancia** | Detectar si el servicio cambia durante el día | Cada 1–2 horas repetir los 20 ejemplos y ~10 secuencias clave | ~300 por día |

El detalle completo de cada prueba está en `plan-exploracion.md`.

### 4.4 Presupuesto

Cada persona tiene un token con 8.000 mensajes por día y un estado propio. Repartimos el trabajo
para explorar en paralelo:

| Quién | Qué |
| --- | --- |
| Dos tokens | Fase 2 (control). Es la que más mensajes consume: hasta 100 por mensaje nuevo |
| Resto del equipo | Fases 3 y 4, en cuanto la fórmula esté resuelta. Cada mensaje cuesta 1 |
| Un token | Fases 0, 1 y 5 |

### 4.5 Cuándo damos la exploración por cerrada

| Criterio | Umbral |
| --- | --- |
| La fórmula del control acierta en mensajes nunca probados | **20 de 20** |
| Acertamos la respuesta exacta en un lote de ~30 secuencias nuevas | **≥ 80 %** |
| Cada comando y cada error tiene al menos una prueba registrada | **100 %** |
| Cada regla que usa el reemplazo se repite en al menos dos secuencias (confirmada) | **100 %** de las reglas de negocio; el resto queda como probable o supuesto |

La fórmula exige el 100 % porque un solo fallo hace que el reemplazo rechace un mensaje que el
original aceptaba, y la secuencia entera falla.

## 5. Cómo se genera `experimentos.jsonl`

El registrador escribe **una línea por cada mensaje enviado al servicio antiguo**, sin excepción.
Eso incluye los resets y cada intento del buscador de control.

| Campo | De dónde sale |
| --- | --- |
| `id` | Número correlativo que asigna el registrador. Es único y no se reutiliza, porque la especificación lo cita como evidencia |
| `seq` | Nombre de la secuencia (ej.: `T2-limite-acumulado`). Cambia en cada reset. Todas las líneas de una secuencia van después de su reset |
| `x_req` | El valor del header `X-Req` de la respuesta (vacío si no viene) |
| `hipotesis` | Empieza con el ID de la regla que se prueba (ver 5.1) y sigue con lo que esperamos que responda, escrito **antes** de mandar el mensaje |
| `request` | El cuerpo enviado tal cual (ej.: `{"m":"ALTA;Lucia;82"}`) |
| `status` | El código que respondió el servicio |
| `response` | El cuerpo que respondió, sin modificar. Si no es JSON se guarda como texto |
| `conclusion` | Se completa después: si la predicción acertó y qué aprendimos |
| `ts` | **Campo agregado por nosotros.** Fecha y hora del envío (ej.: `2026-10-10T14:05:12`). La especificación pide decir **desde cuándo** cambió el servicio, y sin la hora no se puede responder |

Ejemplo de una línea, con el request y la respuesta del ejemplo 9 de `pruebas/ejemplos.jsonl`
(`id`, `seq`, `x_req`, `ts` y el ID de regla son ilustrativos):

```json
{"id": 57, "seq": "T1-limite-exacto", "x_req": 4, "ts": "2026-10-10T14:05:12",
 "hipotesis": "[COM-TRANSFER-03] Con saldo 210000, transferir 120000 da 422 E506 límite excedido",
 "request": {"m": "TRANSFER;AC-0001;AC-0002;120000;55"},
 "status": 422, "response": {"error": "E506", "mensaje": "límite excedido"},
 "conclusion": "Acertó: el límite está por debajo de 120000 aunque haya saldo"}
```

Reglas del registro:

- **Los mensajes que van a otras rutas** (`/health`, `/__reset`, rutas inexistentes) también se
  registran. La ruta y el método se indican en la hipótesis.
- **El token nunca se escribe en el log.** Si la prueba usa un token inválido o ninguno, se indica
  en la hipótesis.
- **Las respuestas por exceso de mensajes** (header `X-Frontier-Infra: rate-limit`) se registran,
  pero se marcan en la conclusión como "límite de infraestructura, no es del servicio" y la prueba
  se repite.
- **El log solo crece.** No se borran ni se editan líneas, salvo la conclusión.

### 5.1 Del log a la especificación

Cada regla tiene un ID con el prefijo de la sección de la especificación donde va. Ese ID va al
inicio de la hipótesis. Para escribir la especificación basta con filtrar el log por ID: las líneas
que aparecen son la evidencia, y cuántas secuencias distintas hay decide la confianza.

| Sección de la especificación | Prefijo | Fase que la alimenta |
| --- | --- | --- |
| Entrada | `ENT` | 1 |
| Integridad | `INT` | 2 |
| Comandos | `COM` | 3 |
| Memoria entre requests | `MEM` | 4 |
| Errores (y su orden) | `ERR` | 3b |
| Cambios durante el día | `CAM` | 0 y 5, con la hora del campo `ts` |
| Riesgos | `RIE` | Sale de los hallazgos de 3 y 4 (ej.: si `ANULA` puede dejar un saldo negativo) |

| Líneas en el log para una regla | Confianza en la especificación |
| --- | --- |
| Ninguna | **supuesto** (lo que hace el reemplazo por defecto) |
| Una secuencia | **probable** |
| Dos o más secuencias con el mismo resultado | **confirmado** |

## 6. Construcción del reemplazo

El reemplazo se construye en dos pasos:

1. **Esqueleto:** las rutas del contrato (`/health`, `/__reset`, `/msg`), la validación del token
   del equipo y las respuestas de la fase 1. Se despliega pronto para validarlo en `/evento`.
2. **Reglas de negocio:** se agregan a medida que la exploración las confirma. Los mensajes de
   respuesta se guardan en un solo lugar, copiados letra por letra del servicio antiguo.

### Decisiones principales

| Decisión | Elegimos | Descartamos | Por qué |
| --- | --- | --- | --- |
| Cuánto generaliza el reemplazo | Reglas generales con evidencia consistente (saldos, numeración, errores vistos) | Responder solo a mensajes idénticos a los observados | Las pruebas son secuencias nuevas. Copiar casos vistos fallaría en casi todas |
| Reglas con más de una explicación | Elegir la que encaja con toda la evidencia y diseñar una prueba que la confirme | Elegir una sin verificar | Solo una prueba decide entre las dos |
| Casos sin evidencia | Comportamiento por defecto, declarado como supuesto | Inventar errores no vistos | Un supuesto declarado no resta; una afirmación falsa sí |
| Si no resolvemos la fórmula del control | Aceptar cualquier control numérico | Rechazar todo con `E202` | La mayoría de las pruebas usan controles válidos. Aceptar todo falla en pocas; rechazar todo falla en casi todas |
| Reglas fijas o un modelo de IA | Reglas fijas en código | Un modelo de IA que responda | La comparación es letra por letra y hay un control que calcular. Un modelo de IA no siempre responde igual |

## 7. Medición

Medimos en tres momentos. Cada uno responde a una pregunta distinta.

| Momento | Pregunta | Cómo | Meta |
| --- | --- | --- | --- |
| **Durante la exploración** | ¿Entendemos el servicio? | Predicciones frente a respuestas reales en lotes de secuencias nuevas (sección 4.5) | ≥ 80 % de aciertos; fórmula del control 20/20 |
| **Al construir** | ¿El reemplazo responde igual que lo registrado? | Repetimos contra el reemplazo **todas** las secuencias de `experimentos.jsonl` y comparamos con lo que respondió el original | 100 % en la versión vigente |
| **Al entregar** | ¿Pasa las pruebas oficiales? | Validamos el reemplazo en `/evento` y leemos el resultado en `/evento/resultados` | Que suba en cada versión |

La comparación usa las mismas reglas que el evaluador:

- el mismo código de respuesta;
- si los dos contenidos son JSON, los datos de un objeto pueden venir en cualquier orden, las listas
  van en el mismo orden y los textos y números tienen que ser idénticos;
- si alguno no es JSON, el texto se compara letra por letra.

Cuando una comparación falla hay dos explicaciones posibles. O el reemplazo tiene un error, o el
servicio antiguo cambió. La vigilancia de la fase 5 permite distinguirlas: si los 20 ejemplos y las
secuencias clave siguen respondiendo igual, el error está en el reemplazo.

Ninguna de estas mediciones hace que el reemplazo llame al servicio antiguo. El reemplazo se compara
con respuestas ya registradas, y solo el registrador habla con el original.
