# Secuencias de exploración

Cada archivo YAML es una secuencia: el ejecutor manda `POST /__reset` y luego cada paso en orden.
Todo queda en `experimentos.jsonl`, con `seq` = `<seq>@<id del reset>`.

```yaml
seq: T2-limite-acumulado        # nombre base; se repite en cada corrida
pasos:
  - regla: COM-TRANSFER-04      # ID de la regla (prefijo = sección de la especificación)
    hipotesis: Dos transferencias de 80000 pasan si el límite es por operación
    m: "TRANSFER;AC-0001;AC-0002;80000;{c}"   # {c}: el buscador pone el control
    espera:                     # predicción; sin ella la conclusión queda vacía
      status: 200
      response: {status: recieved, operacionId: OP-0002}
```

| Clave | Uso |
| --- | --- |
| `regla`, `hipotesis` | Obligatorias. Se escriben antes de correr |
| `m` | Atajo para `POST /msg` con `{"m": ...}`. Si termina en `;{c}`, el control se busca o se toma de `explorador/controles.json` |
| `cuerpo` | Cualquier valor JSON (para `{}`, `{"m": 123}`, arrays...) |
| `crudo` | Texto enviado tal cual (JSON mal escrito, etc.) |
| `metodo`, `ruta` | Por defecto `POST` y `/msg` |
| `auth` | `valido` (defecto), `ninguno` o `invalido` |
| `content_type` | Por defecto `application/json` si hay cuerpo |
| `espera` | `status` más `response` (JSON) o `texto` (respuesta que no es JSON) |

Para no hacer reset al inicio: `reset: false` en la raíz del archivo.

Las comillas evitan sorpresas de YAML: `on`, `yes`, `no` o `0700` sin comillas no son texto.
