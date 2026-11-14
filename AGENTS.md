# AGENTS.md — SecureAssist AI

## 1. IDENTIDAD DEL PROYECTO

- **Nombre:** SecureAssist AI.
- **Descripción:** Aplicación web de asistencia técnica inteligente para instaladores de sistemas de seguridad electrónica.

## 2. OBJETIVO PRINCIPAL

Desarrollar un asistente conversacional que ayude a los instaladores a identificar y solucionar problemas técnicos mediante descripciones en lenguaje natural y fotografías.

## 3. ALCANCE DE LA PRIMERA VERSIÓN

La primera versión se concentrará exclusivamente en el chatbot de asistencia técnica e incluirá:

- Conversaciones en lenguaje natural.
- Recepción de fotografías e interpretación multimodal.
- Preguntas de diagnóstico cuando falte información.
- Recomendaciones prácticas, breves y ordenadas, con alternativas si una solución no funciona.
- Confirmación de resultados por parte del instalador.
- Memoria individual por instalador.
- Consulta de conocimiento técnico compartido.

El inventario de cámaras, accesorios, grabadores y otros equipos, incluidas consultas de existencias, cantidades y precios, es una etapa futura y no debe desarrollarse hasta recibir autorización expresa.

## 4. COMPORTAMIENTO DEL CHATBOT

- Comprender lenguaje coloquial, expresiones cotidianas, descripciones incompletas y errores ortográficos.
- Analizar texto y fotografías de instalaciones y equipos.
- Proponer soluciones prácticas, breves y ordenadas.
- Ofrecer alternativas cuando una solución no funcione.
- Formular preguntas cuando falte información.
- Reconocer cuándo no tiene suficiente información para dar un diagnóstico y no inventar diagnósticos ni especificaciones.
- Advertir sobre riesgos eléctricos y de seguridad.
- Preguntar al instalador si la solución funcionó y registrar su respuesta.
- Presentar las soluciones compartidas con su contexto y procedencia; una confirmación no garantiza que funcionen para todos los modelos o situaciones.

## 5. ARQUITECTURA Y TECNOLOGÍAS APROBADAS

La arquitectura inicial será un monolito modular y utilizará:

- **Frontend:** React + TypeScript.
- **Backend:** Python + FastAPI.
- **Comunicación:** API REST sobre HTTPS.
- **Base de datos:** PostgreSQL mediante Supabase.
- **Infraestructura administrada:** Supabase.
- **Autenticación:** Supabase Auth es la alternativa principal a evaluar.
- **Fotografías:** Supabase Storage con almacenamiento privado y controles de acceso.
- **Aislamiento de datos:** evaluar y configurar políticas Row Level Security (RLS) para proteger los datos de cada instalador.
- **Control de versiones y colaboración:** Git y GitHub.

OpenAI API será el primer proveedor que se evaluará para interpretar texto y fotografías. Se requiere un modelo multimodal. OpenAI es el candidato inicial, pero su selección definitiva dependerá de pruebas técnicas y de la evaluación de costos, calidad y privacidad. Las credenciales de cualquier proveedor de IA deben permanecer exclusivamente en el backend y nunca exponerse al frontend.

La selección de un proveedor o servicio dentro de estas opciones y cualquier cambio arquitectónico importante deben respetar las reglas de aprobación de este documento.

## 6. MEMORIA INDIVIDUAL Y CONOCIMIENTO COMPARTIDO

### 6.1 Memoria individual por instalador

Cada instalador tendrá una memoria independiente que podrá conservar el contexto de sus conversaciones y recordar equipos y soluciones que haya utilizado, evitar preguntas repetitivas y adaptar las respuestas a su experiencia.

- Las conversaciones y datos privados de un instalador no podrán ser consultados por otros instaladores.
- El sistema recuperará únicamente el contexto necesario para cada consulta.
- No se almacenará información personal innecesaria.
- La memoria individual se mantendrá separada del conocimiento compartido.

### 6.2 Conocimiento técnico compartido

Los instaladores podrán consultar casos técnicos compartidos. Cada caso deberá conservar, cuando esté disponible, su procedencia, equipo relacionado, problema, diagnóstico, preguntas relevantes, solución propuesta, resultado y confirmación del instalador.

Un caso podrá incorporarse al conocimiento compartido únicamente si se cumplen ambas condiciones:

1. El instalador confirma que la solución funcionó.
2. El instalador autoriza expresamente compartir el caso.

La confirmación de que una solución funcionó no equivale a autorización para compartirla. No se deben compartir conversaciones privadas. Los casos compartidos deben identificarse como **«confirmados por el instalador»** y conservar el contexto necesario para evitar generalizaciones no verificadas.

## 7. FOTOGRAFÍAS, PRIVACIDAD Y SEGURIDAD

- Las fotografías serán privadas por defecto y no se compartirán automáticamente.
- Solo se incorporarán fotografías a referencias compartidas con autorización expresa.
- Utilizar almacenamiento privado y controles de acceso que impidan que otros instaladores accedan a las imágenes.
- Definir una política de conservación y eliminación de fotografías antes de su puesta en producción.
- Mantener trazabilidad del origen de cada solución y recurso compartido.
- Separar la memoria individual de la base de conocimiento compartida.
- Aplicar buenas prácticas de seguridad informática y proteger la información privada de cada usuario.
- No exponer credenciales, tokens ni secretos en el frontend, el repositorio o los registros.

## 8. TRABAJO POR ETAPAS

- **Etapa 1 — Primera versión del chatbot:** conversaciones en lenguaje natural, fotografías e interpretación multimodal, diagnóstico conversacional, recomendaciones y alternativas, confirmación de resultados, memoria individual y consulta de conocimiento compartido, conforme al consentimiento requerido.
- **Etapa 2 — Pruebas y validación:** validar los flujos funcionales, la calidad de las respuestas, la privacidad y el aislamiento de datos, y corregir problemas aprobados.
- **Etapa 3 — Estabilización y publicación:** preparar la integración general y publicación cuando se autorice.
- **Etapa 4 — Inventario inteligente:** etapa futura; no desarrollar hasta recibir autorización expresa.
- **Etapa 5 — Integraciones futuras:** cualquier integración adicional requiere alcance y autorización específicos.

No avanzar automáticamente a una etapa posterior. La inclusión de fotografías y análisis visual en la Etapa 1 reemplaza la planificación anterior que los ubicaba en una etapa posterior.

## 9. REGLAS DE DESARROLLO

- No desarrollar funcionalidades que no hayan sido aprobadas.
- No modificar archivos sin comprender primero su propósito.
- No instalar dependencias sin autorización.
- No inventar requisitos ni información técnica.
- Mantener el código organizado, modular, comprensible y documentado.
- Evitar código duplicado.
- Priorizar privacidad, seguridad y mantenibilidad.
- Consultar antes de realizar cambios arquitectónicos importantes.
- Antes de implementar una funcionalidad, explicar qué se hará y cómo; esperar aprobación cuando existan decisiones importantes.
- Mantener el proyecto preparado para colaboración mediante GitHub, con documentación clara y estructura comprensible.
- Explicar los cambios realizados.
- Ejecutar pruebas pertinentes cuando se implemente una funcionalidad e informar resultados y limitaciones.
- Trabajar paso a paso y mantener el foco en el alcance autorizado.

## 10. METODOLOGÍA Y COLABORACIÓN

- Comprender el objetivo, alcance, contexto y restricciones antes de actuar.
- Diferenciar hechos comprobados, inferencias y propuestas.
- Realizar cambios mínimos y verificables.
- Revisar el estado del repositorio y evitar sobrescribir trabajo existente antes de operaciones Git importantes.
- No realizar operaciones destructivas, publicar cambios ni afectar sistemas externos sin la autorización requerida.
- Informar problemas fuera del alcance sin modificarlos automáticamente.
- Al finalizar, explicar qué cambió, qué se verificó y qué queda pendiente.
