# CLAUDE.md

Reto 2 · La caja negra. Hay que estudiar desde fuera un servicio HTTP antiguo y construir un
reemplazo que responda **exactamente igual** (mismo status y mismo cuerpo, errores incluidos).
Entrega a las 20:00: el reemplazo desplegado, la especificación y `experimentos.jsonl`.

## Dónde está cada cosa

| Archivo | Contenido |
| --- | --- |
| [README.md](README.md) | Enunciado oficial: contrato del reemplazo, formato del log, secciones de la especificación, evaluación y reglas. Es la fuente de verdad |
| [docs/planning.md](docs/planning.md) | Documento de diseño: el problema, supuestos, las tres piezas (explorar → construir → medir), formato del log y decisiones |
| [docs/plan-exploracion.md](docs/plan-exploracion.md) | Detalle de cada prueba por fase (R1–R22, C1–C8, A/Q/D/T/N, M1–M3), presupuesto y criterio de cierre |
| [docs/arquitectura.svg](docs/arquitectura.svg) | Diagrama de la arquitectura |
| [pruebas/ejemplos.jsonl](pruebas/ejemplos.jsonl) | Los 20 ejemplos oficiales: una sola secuencia tras reset, versión de la mañana |
| `.env` | `BEARER_TOKEN` personal. Nunca mostrarlo, commitearlo ni escribirlo en el log |

Servicio original: `https://caja-negra-production-c64f.up.railway.app` (`POST /msg`,
`POST /__reset`, `GET /health`; header `Authorization: Bearer <token>`).

## Estado actual

Fase de **exploración**: entender cómo responde el original. Todavía no hay código del reemplazo.
El comparador reemplazo vs. original queda para cuando el reemplazo exista. Solo explora una
persona (un token, un único `experimentos.jsonl`).

## Herramienta de exploración

Python 3.12 + uv. `pyproject.toml` y `.venv` van en la raíz (no crear otro entorno); el paquete
está en [explorador/](explorador/). Registrador, ejecutor de secuencias y buscador de control; el
deductor de fórmula viene después. Secuencias en YAML en [secuencias/](secuencias/) (formato en
[secuencias/README.md](secuencias/README.md)). Los comandos se corren desde la raíz.

```bash
uv run explorador correr secuencias/fase1/*.yaml --seco   # muestra sin enviar ni registrar
uv run explorador correr secuencias/fase1/*.yaml          # envía y registra
uv run explorador buscar "DEPOSITO;AC-0001;300000"        # control por fuerza bruta (≤101 req)
uv run explorador cupo                                    # requests de hoy frente a 8.000
uv run explorador diferencias 15:30 [--detalle]           # antes vs. después del corte (solo lee el log)
```

- Probar primero con `--seco`: lo que se manda de verdad queda para siempre en el log.
- **Fórmula del control resuelta** (ISO 7064 MOD 97-10, verificada 20/20): ver
  [explorador/control.py](explorador/control.py). En los YAML, `;{c}` se calcula con ella sin
  gastar requests; solo los mensajes con caracteres sin evidencia (tildes, espacios) pasan por el
  buscador. Pares encontrados por fuerza bruta: `explorador/controles.json`.

## Reglas que no se pueden romper

- **El reemplazo nunca llama al original** (ni a otro reemplazo). Si lo hace, el set vale 0.
- **Todo request al original pasa por el registrador** y queda en `experimentos.jsonl`. Nada de
  `curl` manual: lo que no está registrado no sirve como evidencia.
- **Los defectos del original se copian, no se corrigen**: `"recieved"`, el espacio final en
  `"comando desconocido "`, `cuentaId` frente a `cuenta_id`, fallos de `ANULA` con status 200.
  Los textos de respuesta se copian letra por letra en un solo lugar.
- **No inventar errores ni reglas sin evidencia.** Lo no probado se implementa con un comportamiento
  por defecto y se declara como **supuesto**. Una afirmación falsa en la especificación resta.
- Respuestas con header `X-Frontier-Infra: rate-limit` son de infraestructura: se registran, se
  marcan así en la conclusión y la prueba se repite.
- Límites por token: 10 req/s y 8.000 req/día. Cada paso del reemplazo tiene 5 s para responder y
  el set habla con un solo proceso (el estado vive en memoria de ese proceso).

## Convenciones del log (`experimentos.jsonl`)

Campos del README más `ts` (fecha y hora del envío). Ver `docs/planning.md` sección 5.

- `id` correlativo, único, nunca se reutiliza. El log solo crece; solo se edita `conclusion`.
- Una línea por cada request, incluidos resets, rutas no `/msg` e intentos del buscador de control.
- `seq` cambia en cada reset; todas sus líneas van después de ese reset.
- `hipotesis` se escribe **antes** de enviar, empieza con el ID de la regla y predice status y
  cuerpo exactos. Ej.: `[COM-TRANSFER-03] Con saldo 210000, transferir 120000 da 422 E506 ...`
- Prefijos de ID = secciones de la especificación: `ENT` Entrada, `INT` Integridad, `COM` Comandos,
  `MEM` Memoria, `ERR` Errores y su orden, `CAM` Cambios durante el día, `RIE` Riesgos.
- Confianza: ninguna línea → **supuesto**; una secuencia → **probable**; dos o más secuencias
  distintas con el mismo resultado → **confirmado**.

## Comparación de respuestas

Igual que el evaluador: mismo status; si ambos cuerpos son JSON, claves en cualquier orden, arrays
en el mismo orden, strings y números idénticos; si alguno no es JSON, texto exacto.

## Preferencias de trabajo

- El esfuerzo va a la lógica de negocio: el control, los comandos, el orden de errores y la memoria
  entre requests. Nada de pruebas en variantes triviales de entrada (mayúsculas en `Bearer`, etc.).
  La forma del cuerpo sí se prueba, en versión mínima (R13–R22), porque la especificación la pide.
- Autenticación: solo token ausente y token inválido. Sí una prueba mínima de rutas y métodos
  desconocidos.
- Cierre de la exploración: ≥ 80 % de predicciones acertadas en un lote de ~30 secuencias nuevas, y
  la fórmula del control 20/20 (ver `docs/plan-exploracion.md` sección 6).
- Documentos y respuestas en español.
