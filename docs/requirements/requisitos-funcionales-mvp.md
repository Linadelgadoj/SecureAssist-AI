# SecureAssist AI — Requisitos funcionales del MVP

**Versión:** 1.0 — para revisión y aprobación  
**Estado:** especificación funcional; no define endpoints, esquema físico de datos ni implementación.  
**Fuentes de decisión:** AGENTS.md, docs/architecture/arquitectura-tecnica.md y docs/architecture/comportamiento-chatbot.md.

## 1. Propósito y convenciones

Este documento define de forma verificable el comportamiento esperado de la primera versión web de SecureAssist AI: asistencia técnica conversacional para instaladores de sistemas de seguridad electrónica, con entrada de texto y fotografías, diagnóstico iterativo, memoria privada individual y consulta de casos técnicos compartidos que cumplan las reglas de consentimiento.

Cada requisito funcional tiene código RF único, módulo, prioridad, descripción, actor, precondiciones, flujo principal, alternativas, errores, resultado y criterios de aceptación. Los criterios describen resultados que pueden convertirse en pruebas funcionales.

### Prioridades

- **Crítica:** sin ella se incumple una regla central de privacidad, seguridad o consentimiento, o no puede completarse el flujo principal.
- **Alta:** necesaria para el alcance comprometido del MVP.
- **Media:** incluida o condicionada en el MVP; depende de una decisión pendiente o configuración de proveedor.
- **Baja:** mejora aplazable sin impedir el flujo esencial.

### Actores

- **Instalador autenticado:** usuario de la aplicación.
- **Asistente:** componente conversacional que interpreta problemas y presenta preguntas o recomendaciones.
- **Servicios externos:** autenticación, almacenamiento, base de datos y proveedor multimodal.

No se definen roles administrativos porque no son necesarios para el alcance aprobado.

## 2. Alcance del MVP

El MVP comprende autenticación de instaladores, conversación en lenguaje natural, fotografías, diagnóstico, recomendaciones seguras, seguimiento de resultados, historial, memoria individual, registro conceptual de casos y consulta de conocimiento técnico compartido. Un caso solo se comparte con confirmación positiva y autorización expresa para el texto; las fotografías requieren autorización independiente.

Quedan fuera el catálogo comercial, inventario de equipos, existencias, cantidades, precios, cotizaciones, compras, ventas, proveedores e integración con inventarios externos. No se especifica su diseño futuro.

> **Actualización 2026-11-19:** se autorizó y se implementó el inventario para reparaciones: existencias por ubicación, movimientos, clientes, equipos instalados e historial de reparaciones, con roles de administrador y técnico. Siguen excluidos el catálogo comercial, los precios, las cotizaciones, las compras, las ventas, los proveedores y los inventarios externos. Ver [inventario-y-asistente.md](../architecture/inventario-y-asistente.md).

## 3. Requisitos funcionales

En cada ficha, «aceptación» contiene comprobaciones observables. Los límites marcados como propuestos son valores iniciales que requieren validación antes de fijarse para producción.

### Módulo 1. Gestión de usuarios y autenticación

#### RF-001 — Registro de instalador
- **Módulo/prioridad/actor:** 1 / Alta / visitante.
- **Descripción:** permitir crear una cuenta individual mediante el servicio de autenticación configurado, solicitando solo datos necesarios para ese flujo.
- **Precondiciones:** no hay sesión autenticada.
- **Flujo principal:** visitante ingresa los datos requeridos; el servicio valida el registro; la interfaz informa alta o verificación pendiente.
- **Alternativas y errores:** indicar campos inválidos o que el servicio no está disponible, sin revelar datos de otras cuentas.
- **Resultado:** cuenta creada o estado pendiente claramente informado.
- **Aceptación:** datos válidos producen alta/verificación; inválidos permiten corregir; falla del proveedor no crea sesión ficticia.

#### RF-002 — Inicio de sesión
- **Módulo/prioridad/actor:** 1 / Crítica / instalador registrado.
- **Descripción:** autenticar usando Supabase Auth si se aprueba su configuración, o la alternativa que se apruebe.
- **Precondiciones:** cuenta registrada y servicio disponible.
- **Flujo principal:** usuario envía credenciales; sistema valida y abre el espacio privado de la identidad autenticada.
- **Alternativas y errores:** credenciales incorrectas generan mensaje genérico; falta de conexión permite reintentar.
- **Resultado:** sesión asociada a la identidad verificada.
- **Aceptación:** credenciales válidas permiten entrar; inválidas no revelan existencia de cuenta; sin sesión no se accede a datos privados.

#### RF-003 — Cierre de sesión
- **Módulo/prioridad/actor:** 1 / Alta / instalador autenticado.
- **Descripción:** terminar la sesión actual y ocultar información privada.
- **Precondiciones:** existe sesión activa.
- **Flujo principal:** usuario elige cerrar sesión; el servicio cierra/invalida la sesión; la interfaz vuelve al acceso.
- **Alternativas y errores:** si no puede confirmarse el cierre remoto, bloquear la vista privada e informar el estado.
- **Resultado:** se requiere nueva autenticación para consultar datos privados.
- **Aceptación:** navegación atrás no expone historial; una solicitud sin sesión es rechazada.

#### RF-004 — Recuperación de acceso y vencimiento de sesión
- **Módulo/prioridad/actor:** 1 / Media / instalador.
- **Descripción:** ofrecer recuperación si el proveedor aprobado la contempla; al vencer sesión, exigir autenticación nueva.
- **Precondiciones:** cuenta registrada; recuperación habilitada para usar ese flujo.
- **Flujo principal:** usuario solicita recuperación; el proveedor gestiona la operación. Sesión vencida bloquea operaciones privadas.
- **Alternativas y errores:** si el flujo no está habilitado, explicarlo; mensajes no revelan si una cuenta existe.
- **Resultado:** acceso recuperado por mecanismo configurado o datos privados bloqueados.
- **Aceptación:** sesión vencida no lee ni guarda información; sistema no inventa un proceso de recuperación inexistente.

#### RF-005 — Identidad y autorización por recurso
- **Módulo/prioridad/actor:** 1 / Crítica / sistema.
- **Descripción:** validar identidad en backend y comprobar propiedad/permisos de conversación, mensaje, fotografía y memoria. Un identificador recibido del navegador no demuestra propiedad.
- **Precondiciones:** solicitud a recurso protegido.
- **Flujo principal:** sistema valida sesión, identifica al usuario y comprueba propiedad o disponibilidad compartida autorizada.
- **Alternativas y errores:** denegar acceso inválido/ajeno sin revelar contenido ni propietario.
- **Resultado:** cada usuario accede solo a lo propio y a casos compartidos vigentes.
- **Aceptación:** dos cuentas de prueba no leen entre sí; alterar ID no concede acceso; recurso ajeno se deniega.

### Módulo 2. Interfaz y conversación

#### RF-006 — Pantalla principal adaptable
- **Módulo/prioridad/actor:** 2 / Alta / instalador autenticado.
- **Descripción:** mostrar conversación, entrada de texto, adjuntos, estado de procesamiento, errores, acción de nuevo chat e historial, con lenguaje sencillo y adaptación a computador, tableta y móvil.
- **Precondiciones:** sesión válida.
- **Flujo principal:** usuario accede al chat; sistema presenta controles principales o estado vacío.
- **Alternativas y errores:** componente que no carga informa el problema y conserva disponibles los demás cuando sea posible.
- **Resultado:** interfaz utilizable sin conocimientos informáticos avanzados.
- **Aceptación:** flujo principal se completa en tamaños móvil y escritorio sin desplazamiento horizontal de página; estado vacío permite iniciar.

#### RF-007 — Iniciar conversación nueva
- **Módulo/prioridad/actor:** 2 / Alta / instalador autenticado.
- **Descripción:** crear contexto nuevo sin borrar historial ni importar automáticamente resultados anteriores.
- **Precondiciones:** sesión válida.
- **Flujo principal:** usuario elige nueva conversación; sistema muestra espacio vacío listo para mensaje.
- **Alternativas y errores:** error de creación se informa y no se simula éxito.
- **Resultado:** nuevo contexto privado separado.
- **Aceptación:** mensaje nuevo no aparece en conversación previa; las anteriores permanecen; nuevo chat no hereda diagnóstico como actual.

#### RF-008 — Enviar mensaje de texto
- **Módulo/prioridad/actor:** 2 / Crítica / instalador autenticado.
- **Descripción:** recibir descripción coloquial, con errores ortográficos o incompleta y asociarla al problema actual.
- **Precondiciones:** sesión y conversación activas.
- **Flujo principal:** usuario escribe y envía; sistema muestra el mensaje y comienza procesamiento.
- **Alternativas y errores:** mensaje vacío no se envía; pérdida de red indica que el mensaje no fue confirmado y conserva borrador en la vista activa.
- **Resultado:** mensaje recibido o estado de error inequívoco.
- **Aceptación:** mensaje no vacío aparece como usuario; texto vacío no genera consulta; borrador fallido no se muestra como enviado ni como respuesta.

#### RF-009 — Respuestas, procesamiento y errores visibles
- **Módulo/prioridad/actor:** 2 / Alta / instalador autenticado.
- **Descripción:** diferenciar mensajes del usuario y asistente, indicar procesamiento y mostrar respuesta en orden.
- **Precondiciones:** consulta enviada.
- **Flujo principal:** mostrar indicador mientras se espera; retirar al obtener respuesta; agregarla al intercambio.
- **Alternativas y errores:** timeout o fallo se presentan como error recuperable, no como diagnóstico.
- **Resultado:** usuario conoce si consulta está pendiente, contestada o fallida.
- **Aceptación:** indicador aparece/desaparece correctamente; mensajes mantienen orden; error se distingue de recomendación.

#### RF-010 — Continuar conversación abierta
- **Módulo/prioridad/actor:** 2 / Alta / instalador autenticado.
- **Descripción:** continuar el contexto seleccionado sin mezclar conversaciones o usuarios.
- **Precondiciones:** conversación propia abierta.
- **Flujo principal:** usuario envía turno; sistema lo vincula al contexto correcto y recupera solo contexto pertinente.
- **Alternativas y errores:** conversación inexistente o ajena se rechaza sin revelar contenido.
- **Resultado:** continuidad del problema asociado.
- **Aceptación:** respuesta a una pregunta se asocia al chat correcto; IDs ajenos no abren conversación; chat nuevo no modifica el anterior.

### Módulo 3. Análisis de fotografías

#### RF-011 — Adjuntar imágenes dentro de límites propuestos
- **Módulo/prioridad/actor:** 3 / Alta / instalador autenticado.
- **Descripción:** permitir fotos asociadas al mensaje. Propuesta inicial para validar: JPEG/JPG, PNG y WebP; máximo 3 imágenes por mensaje y 10 MB por imagen. Estos límites no son restricciones confirmadas del proveedor y deben validarse con modelo multimodal y pruebas.
- **Precondiciones:** conversación autenticada.
- **Flujo principal:** usuario selecciona imagen(es); interfaz muestra vista previa y permite quitar antes de enviar.
- **Alternativas y errores:** tipo, cantidad o peso excedidos se explican y permiten corregir.
- **Resultado:** adjuntos aceptados y asociados al mensaje.
- **Aceptación:** válidos dentro del límite pasan a validación; más de 3, mayor de 10 MB o tipo no permitido se rechaza sin análisis.

#### RF-012 — Validar archivo
- **Módulo/prioridad/actor:** 3 / Crítica / sistema.
- **Descripción:** validar tipo real, peso, contenido legible e integridad en servidor; no confiar solo en extensión ni navegador.
- **Precondiciones:** adjunto recibido.
- **Flujo principal:** sistema valida cada archivo y procesa únicamente formatos/límites aprobados.
- **Alternativas y errores:** archivo corrupto o tipo discrepante se rechaza con indicación de cuál corregir.
- **Resultado:** archivo inválido no llega al modelo ni se publica.
- **Aceptación:** renombrar extensión no evade validación; archivo corrupto falla comprensiblemente; archivos válidos restantes mantienen su asociación.

#### RF-013 — Analizar texto e imagen en conjunto
- **Módulo/prioridad/actor:** 3 / Alta / asistente.
- **Descripción:** relacionar imagen con mensaje, conversación y problema; enviarlos al proveedor multimodal aprobado junto con contexto mínimo.
- **Precondiciones:** texto e imagen validados, usuario autenticado y servicio disponible.
- **Flujo principal:** backend conserva asociaciones; modelo analiza ambos; respuesta distingue observaciones visuales de hipótesis.
- **Alternativas y errores:** fallo de análisis se informa; no se afirma haber visto imagen que no fue procesada.
- **Resultado:** respuesta vinculada al problema y evidencia correctos.
- **Aceptación:** fotos de hilos distintos no se mezclan; la imagen se interpreta junto al texto; salida incierta no inventa identificación.

#### RF-014 — Tratar imagen ilegible y solicitar evidencia adicional
- **Módulo/prioridad/actor:** 3 / Alta / asistente.
- **Descripción:** decir cuando etiqueta, componente o conexión no se distinguen y pedir otra foto concreta solo si puede cambiar el diagnóstico.
- **Precondiciones:** imagen borrosa, incompleta o irrelevante.
- **Flujo principal:** informar límite; solicitar detalle enfocado o modelo por texto.
- **Alternativas y errores:** si no puede aportar foto, continuar con preguntas textuales seguras o reconocer límite.
- **Resultado:** incertidumbre explícita y petición útil.
- **Aceptación:** imagen ilegible no produce marca/modelo inventado; petición indica qué fotografiar; no pide tocar conexiones energizadas ni mostrar credenciales.

#### RF-015 — Privacidad de fotografías
- **Módulo/prioridad/actor:** 3 / Crítica / sistema.
- **Descripción:** almacenar fotos en espacio privado asociado al propietario; acceso solo autenticado y autorizado. No compartir por defecto.
- **Precondiciones:** archivo aceptado.
- **Flujo principal:** asociar con dueño, conversación y problema; permitir procesamiento del backend para esa consulta.
- **Alternativas y errores:** fallo de almacenamiento no permite usar ruta pública como reemplazo.
- **Resultado:** archivo no visible para otro instalador sin consentimiento específico.
- **Aceptación:** cuenta distinta no abre foto; permiso de texto no concede acceso a foto; falla conserva privacidad.

### Módulo 4. Diagnóstico técnico interactivo

#### RF-016 — Interpretar lenguaje cotidiano
- **Módulo/prioridad/actor:** 4 / Alta / asistente.
- **Descripción:** comprender coloquialismos y errores de escritura por contexto, y separar observaciones, hipótesis y datos desconocidos.
- **Precondiciones:** mensaje recibido.
- **Flujo principal:** reformular brevemente lo entendido; preguntar si término admite significados técnicos diferentes.
- **Alternativas y errores:** no elegir en silencio una interpretación que cambie el procedimiento.
- **Resultado:** intención comprendida o ambigüedad identificada.
- **Aceptación:** falta ortográfica no bloquea; no corrige al usuario; ambigüedad técnica produce pregunta.

#### RF-017 — Identificar síntoma, equipo y alcance
- **Módulo/prioridad/actor:** 4 / Alta / asistente.
- **Descripción:** extraer síntoma observado, equipo afectado y alcance conocido sin inferir marca/modelo.
- **Precondiciones:** problema descrito o síntoma nuevo.
- **Flujo principal:** resumir hechos; marcar desconocidos; pedir dato solo si cambia el paso.
- **Alternativas y errores:** equipo no identificado permite descripción general segura o petición de etiqueta/modelo.
- **Resultado:** contexto de trabajo verificable y corregible.
- **Aceptación:** no añade marca/modelo ausente; distingue relato de hipótesis; instalador puede corregir resumen.

#### RF-018 — Preguntar información faltante sin repetición
- **Módulo/prioridad/actor:** 4 / Alta / asistente.
- **Descripción:** consultar la incertidumbre que determine siguiente paso y revisar conversación/memoria pertinente antes de preguntar.
- **Precondiciones:** falta información relevante.
- **Flujo principal:** hacer pregunta breve y observable; actualizar contexto con respuesta.
- **Alternativas y errores:** ambigüedad permite precisar solo ese dato; dato irrelevante no bloquea orientación segura.
- **Resultado:** aclaración dirigida.
- **Aceptación:** no repite respuesta clara vigente; pregunta impacta decisión; no solicita credenciales.

#### RF-019 — Separar problemas diferentes
- **Módulo/prioridad/actor:** 4 / Alta / asistente.
- **Descripción:** mantener separado cada síntoma/equipo/acción/resultado; asociar síntoma nuevo solo si usuario confirma relación o evidencia suficiente.
- **Precondiciones:** síntoma nuevo o equipo distinto en chat.
- **Flujo principal:** si relación dudosa, preguntar si es el mismo equipo/problema; crear hilo de problema separado cuando sea independiente.
- **Alternativas y errores:** mientras no se aclare, no trasladar resultados entre problemas.
- **Resultado:** diagnósticos no mezclados.
- **Aceptación:** resultado de cámara A no se atribuye a B; síntoma independiente genera aclaración; problema anterior conserva su estado.

#### RF-020 — Reconocer límites y escalar
- **Módulo/prioridad/actor:** 4 / Crítica / asistente.
- **Descripción:** no emitir diagnóstico concluyente si falta evidencia, identificación o documentación necesaria; solicitar datos, dar comprobación segura o escalar.
- **Precondiciones:** evidencia insuficiente o recomendación no validable.
- **Flujo principal:** indicar qué no puede confirmar y qué dato/documento falta; sugerir manual oficial o personal calificado si procede.
- **Alternativas y errores:** nunca completar procedimiento por conjetura.
- **Resultado:** límite técnico claro.
- **Aceptación:** procedimientos incompatibles generan pregunta; documentación ausente no genera paso inventado; hay alternativa o escalamiento claro.

### Módulo 5. Generación de recomendaciones técnicas

#### RF-021 — Presentar pasos verificables
- **Módulo/prioridad/actor:** 5 / Alta / asistente.
- **Descripción:** usar lenguaje sencillo, pasos numerados, qué revisar/hacer y resultado observable esperado; uno a la vez cuando el resultado determine el siguiente.
- **Precondiciones:** existe comprobación compatible y segura.
- **Flujo principal:** expresar interpretación como hipótesis si corresponde; dar paso y esperar resultado.
- **Alternativas y errores:** si no se puede describir resultado, aclarar o escalar.
- **Resultado:** instalador sabe qué hacer y reportar.
- **Aceptación:** recomendación incluye acción y resultado; hipótesis no aparece como causa confirmada; paso siguiente depende del resultado recibido.

#### RF-022 — Dar alternativas sin repetir
- **Módulo/prioridad/actor:** 5 / Alta / asistente.
- **Descripción:** al recibir fallo, mejoría parcial o temporal, actualizar hipótesis y ofrecer siguiente pregunta, alternativa o escalamiento; evitar repetir pasos ya intentados.
- **Precondiciones:** resultado asociado a un paso.
- **Flujo principal:** reconocer resultado y equipo; seleccionar alternativa segura basada en evidencia.
- **Alternativas y errores:** si alternativa depende de equipo desconocido, preguntar primero.
- **Resultado:** diagnóstico avanza sin ciclos innecesarios.
- **Aceptación:** paso intentado queda distinguido; no se repite sin razón explicada; alternativa respeta evidencia actual.

#### RF-023 — Controlar acciones de alto impacto
- **Módulo/prioridad/actor:** 5 / Crítica / asistente e instalador.
- **Descripción:** restablecimiento de fábrica, cambios que puedan borrar configuración, interrumpir servicio o dañar equipo requieren explicar efectos, identificar equipo y procedimiento oficial, verificar respaldo/recuperación y obtener aceptación expresa. No guiar si falta una condición.
- **Precondiciones:** se considera una acción de impacto.
- **Flujo principal:** detenerse; explicar consecuencias; verificar modelo/documentación, respaldo y acceso de recuperación; pedir aceptación explícita antes de instruir.
- **Alternativas y errores:** desconocimiento o imposibilidad de verificar provoca detención y escalamiento.
- **Resultado:** ninguna acción destructiva se recomienda casualmente.
- **Aceptación:** reset no se propone como primer paso; falta de respaldo o modelo impide instrucciones; respuesta ambigua no cuenta como aceptación.

### Módulo 6. Seguimiento de problemas y soluciones

#### RF-024 — Clasificar resultado
- **Módulo/prioridad/actor:** 6 / Crítica / instalador y asistente.
- **Descripción:** clasificar lenguaje del usuario como solución confirmada, mejora parcial, solución temporal, no funcionó, no probado o ambiguo.
- **Precondiciones:** recomendación entregada.
- **Flujo principal:** preguntar si funcionó; interpretar; aclarar si no se entiende.
- **Alternativas y errores:** mejora parcial/temporal mantiene el caso abierto; no probado queda pendiente.
- **Resultado:** estado refleja lo reportado.
- **Aceptación:** “mejoró pero sigue” = parcial; “sirvió y volvió” = temporal; éxito completo claro = confirmado; silencio/no prueba no es éxito.

#### RF-025 — Registrar pasos y resultados
- **Módulo/prioridad/actor:** 6 / Alta / sistema.
- **Descripción:** conservar en contexto privado procedimiento, equipo/problema, orden y resultado de cada comprobación.
- **Precondiciones:** usuario comunica resultado.
- **Flujo principal:** asociar resultado a recomendación y problema correctos.
- **Alternativas y errores:** si no se guarda, informar; no decir que quedó registrado.
- **Resultado:** memoria útil para no repetir pruebas.
- **Aceptación:** cada resultado vinculado a paso; fallidos y positivos distinguibles; resultados de problemas distintos no se mezclan.

#### RF-026 — Continuar según clasificación
- **Módulo/prioridad/actor:** 6 / Alta / asistente.
- **Descripción:** no cerrar parcial/temporal; registrar fallo y continuar; esperar ante no probado; aclarar ambigüedad; tras éxito ofrecer consentimiento sin implicarlo.
- **Precondiciones:** resultado clasificado.
- **Flujo principal:** aplicar transición correspondiente de la sección 8.
- **Alternativas y errores:** no reiniciar pasos ya intentados.
- **Resultado:** conversación continúa de forma consistente con evidencia.
- **Aceptación:** parcial y temporal siguen abiertos; no probado no se trata como fallo; éxito puede permanecer privado.

### Módulo 7. Historial de conversaciones

#### RF-027 — Listar historial propio
- **Módulo/prioridad/actor:** 7 / Alta / instalador autenticado.
- **Descripción:** mostrar conversaciones propias con título legible y fechas disponibles de creación/última actividad.
- **Precondiciones:** sesión válida.
- **Flujo principal:** consultar historial; ordenar por actividad reciente; ofrecer abrir.
- **Alternativas y errores:** historial vacío muestra estado vacío; error permite reintentar.
- **Resultado:** acceso a conversaciones anteriores propias.
- **Aceptación:** nunca aparece chat de otra cuenta; fechas se muestran cuando existen; vacío no se presenta como error.

#### RF-028 — Abrir conversación anterior
- **Módulo/prioridad/actor:** 7 / Alta / instalador autenticado.
- **Descripción:** mostrar mensajes, problemas, resultados y fotos aún disponibles en orden, tras validar propiedad.
- **Precondiciones:** conversación propia existente.
- **Flujo principal:** usuario elige conversación; sistema valida; presenta historial y estado.
- **Alternativas y errores:** recurso ajeno se deniega; imagen retirada se identifica como no disponible sin bloquear texto.
- **Resultado:** historial consultable y privado.
- **Aceptación:** orden temporal correcto; recurso ajeno no revela contenido; foto no se sustituye por otra.

#### RF-029 — Continuar o crear una conversación
- **Módulo/prioridad/actor:** 7 / Alta / instalador autenticado.
- **Descripción:** al regresar, permitir continuar conversación seleccionada o crear una nueva sin borrar anteriores.
- **Precondiciones:** sesión válida.
- **Flujo principal:** continuar recupera contexto pertinente; nuevo chat empieza separado.
- **Alternativas y errores:** contexto incompleto se indica y no se presume.
- **Resultado:** continuidad elegida por usuario.
- **Aceptación:** mensajes siguen chat abierto; nuevo no borra ni importa automáticamente diagnósticos anteriores; información no cargada puede preguntarse de nuevo.

### Módulo 8. Memoria individual

#### RF-030 — Conservar memoria técnica individual
- **Módulo/prioridad/actor:** 8 / Alta / sistema.
- **Descripción:** conservar equipos, problemas, procedimientos, resultados y soluciones confirmadas del instalador autenticado, sujeto a política de retención pendiente.
- **Precondiciones:** interacción privada guardada.
- **Flujo principal:** vincular hechos a identidad y problema de origen.
- **Alternativas y errores:** no guardar información personal innecesaria; informar error de persistencia.
- **Resultado:** contexto privado útil.
- **Aceptación:** datos se vinculan al usuario correcto; no se agrega información de otro usuario; no se inventa dato ausente.

#### RF-031 — Recuperar contexto pertinente
- **Módulo/prioridad/actor:** 8 / Alta / asistente.
- **Descripción:** recuperar solo memoria relacionada con problema actual para adaptar respuesta y evitar preguntas repetidas.
- **Precondiciones:** usuario autenticado y consulta activa.
- **Flujo principal:** identificar equipo/problema; recuperar contexto necesario; confirmar si vigencia incierta.
- **Alternativas y errores:** información irrelevante o dudosa no se usa como hecho.
- **Resultado:** respuesta contextual sin historial completo innecesario.
- **Aceptación:** recuerdo de otro equipo no altera diagnóstico; dato incierto se confirma; contexto se limita a lo pertinente.

#### RF-032 — Aislar memoria individual
- **Módulo/prioridad/actor:** 8 / Crítica / sistema.
- **Descripción:** impedir lectura por otros instaladores y evitar transferencia automática al conocimiento compartido.
- **Precondiciones:** cualquier lectura o escritura de memoria.
- **Flujo principal:** validar propietario y mantener fuente privada separada.
- **Alternativas y errores:** acceso no autorizado se deniega sin divulgar dato.
- **Resultado:** memoria privada por usuario.
- **Aceptación:** cuenta B no recupera memoria A; confirmación sola no publica; publicar requiere permiso separado.

### Módulo 9. Registro de casos técnicos

#### RF-033 — Mantener datos funcionales del caso
- **Módulo/prioridad/actor:** 9 / Alta / sistema.
- **Descripción:** organizar identificador, instalador de origen, síntoma inicial, equipo, marca/modelo si se conocen, contexto, procedimientos, resultado de cada comprobación, solución asociada al resultado positivo, limitaciones, desconocidos, estado, confirmación y permisos.
- **Precondiciones:** problema iniciado.
- **Flujo principal:** añadir hechos conforme se conocen, vinculados al problema.
- **Alternativas y errores:** lo no informado permanece desconocido; campos opcionales no bloquean conversación.
- **Resultado:** expediente trazable sin suposiciones.
- **Aceptación:** problemas distinguibles; modelo ausente señalado como desconocido; cada comprobación conserva resultado propio.

#### RF-034 — Separar caso privado de versión compartible
- **Módulo/prioridad/actor:** 9 / Crítica / sistema.
- **Descripción:** mantener expediente individual completo separado de versión depurada que pudiera compartirse.
- **Precondiciones:** caso confirmado y posible oferta de consentimiento.
- **Flujo principal:** preparar vista previa solo con datos propuestos; no publicar conversación original.
- **Alternativas y errores:** falta de condición/permiso mantiene todo privado.
- **Resultado:** minimización de datos con procedencia interna protegida.
- **Aceptación:** texto completo no aparece en base compartida; desconocidos no se rellenan; cancelar vista previa no publica.

#### RF-035 — Estado y procedencia
- **Módulo/prioridad/actor:** 9 / Alta / sistema.
- **Descripción:** distinguir privado, no probado, parcial, temporal, fallido, confirmado, compartido autorizado y retirado; conservar origen.
- **Precondiciones:** caso nuevo o actualización.
- **Flujo principal:** actualizar estado solo al recibir evidencia/consentimiento correspondiente.
- **Alternativas y errores:** no permitir transición de parcial/temporal a resuelto sin confirmación nueva.
- **Resultado:** estado fiel y verificable.
- **Aceptación:** parcial no consta como confirmado; revocado no se recupera en compartido; procedencia está disponible sin revelar identidad a lectores.

### Módulo 10. Conocimiento técnico compartido

#### RF-036 — Elegibilidad para compartir texto
- **Módulo/prioridad/actor:** 10 / Crítica / sistema.
- **Descripción:** incorporar texto depurado únicamente con confirmación positiva de resolución completa y autorización expresa vigente para compartir texto.
- **Precondiciones:** estado y permiso registrables.
- **Flujo principal:** comprobar ambas condiciones independientemente; habilitar solo versión autorizada.
- **Alternativas y errores:** faltar cualquiera, silencio o error de guardado mantiene caso privado.
- **Resultado:** compartir nunca se deriva solo de confirmar.
- **Aceptación:** éxito sin permiso no comparte; permiso sin éxito no comparte; parcial, temporal, no probado, fallo o ambiguo no se comparten como solución confirmada.

#### RF-037 — Solicitar autorización textual informada
- **Módulo/prioridad/actor:** 10 / Crítica / instalador autenticado.
- **Descripción:** tras éxito, mostrar qué versión depurada se compartiría y pedir acción afirmativa separada de la confirmación.
- **Precondiciones:** solución confirmada; caso no publicado.
- **Flujo principal:** revisar contenido; usuario autoriza; registrar decisión asociada a la versión.
- **Alternativas y errores:** rechazo, silencio o cancelación mantiene privacidad; cambio sustancial exige nueva autorización.
- **Resultado:** consentimiento específico.
- **Aceptación:** usuario puede revisar texto; no hay opción preseleccionada; edición sustancial no usa consentimiento antiguo.

#### RF-038 — Consultar caso aplicable
- **Módulo/prioridad/actor:** 10 / Alta / instalador y asistente.
- **Descripción:** recuperar solo casos autorizados vigentes; comparar síntoma, tipo, modelo disponible y contexto; comunicar semejanzas/diferencias y procedencia no personal.
- **Precondiciones:** consulta autenticada y casos elegibles existentes.
- **Flujo principal:** buscar referencia; evaluar aplicabilidad; presentarla como experiencia condicional.
- **Alternativas y errores:** sin coincidencia no inventar referencias; diferencia importante provoca aclaración o descarte.
- **Resultado:** uso contextual, no universal.
- **Aceptación:** privado/revocado no se devuelve; referencia indica confirmación del instalador; discrepancia se explica; sin caso no se inventa.

#### RF-039 — Retirar caso del conocimiento compartido
- **Módulo/prioridad/actor:** 10 / Crítica / instalador autenticado.
- **Descripción:** al revocar texto, dejar de devolver/mostrar caso en nuevas consultas compartidas y comunicar estado; no afirmar borrado físico total no verificado.
- **Precondiciones:** autorización textual vigente.
- **Flujo principal:** usuario revoca; sistema desactiva disponibilidad compartida y registra revocación.
- **Alternativas y errores:** tratamiento de copias y respaldos sigue política pendiente; informar qué falta resolver.
- **Resultado:** caso no se expone en nuevas consultas.
- **Aceptación:** búsqueda posterior no devuelve caso; permiso de imagen se evalúa aparte; no se afirma borrado no confirmado.

### Módulo 11. Privacidad, permisos y consentimiento

#### RF-040 — Aislar recursos privados
- **Módulo/prioridad/actor:** 11 / Crítica / sistema.
- **Descripción:** proteger conversaciones, mensajes, fotos y memoria por identidad autenticada usando autorización de backend y RLS cuando se apruebe/configure.
- **Precondiciones:** operación sobre recurso privado.
- **Flujo principal:** verificar usuario/propiedad antes de leer o cambiar.
- **Alternativas y errores:** denegar por defecto si identidad o permiso no se pueden comprobar.
- **Resultado:** separación entre instaladores.
- **Aceptación:** pruebas con cuentas separadas impiden lecturas/escrituras cruzadas; fallo de autorización no devuelve contenido.

#### RF-041 — Autorización independiente de fotografías
- **Módulo/prioridad/actor:** 11 / Crítica / instalador autenticado.
- **Descripción:** pedir consentimiento expreso para cada foto o conjunto claramente identificado; permiso del texto no autoriza imagen.
- **Precondiciones:** imagen privada candidata a referencia.
- **Flujo principal:** mostrar imágenes concretas; usuario selecciona y autoriza; registrar decisión separadamente.
- **Alternativas y errores:** ausencia de decisión, rechazo o fallo al guardar deja imagen privada.
- **Resultado:** solo foto expresamente autorizada puede compartirse junto a caso elegible.
- **Aceptación:** permiso de texto sin imagen comparte solo texto; foto no seleccionada no aparece; silencio no autoriza.

#### RF-042 — Rechazo, silencio y revocación
- **Módulo/prioridad/actor:** 11 / Crítica / usuario y sistema.
- **Descripción:** rechazo/silencio mantiene privacidad; revocación retira el recurso afectado de acceso compartido. Texto e imagen tienen permisos independientes.
- **Precondiciones:** consentimiento ofrecido o vigente.
- **Flujo principal:** registrar decisión; revocar bloquea futuras búsquedas/entregas; solicitar eliminación según política aprobada.
- **Alternativas y errores:** si no se puede verificar borrado de copias, comunicar limitación.
- **Resultado:** decisión respetada y alcance transparente.
- **Aceptación:** silencio/rechazo no comparte; revocar texto retira texto; revocar foto impide su nuevo acceso aunque texto siga autorizado.

#### RF-043 — Minimizar información sensible
- **Módulo/prioridad/actor:** 11 / Crítica / asistente y sistema.
- **Descripción:** no pedir contraseñas, claves WiFi, tokens ni códigos de recuperación; excluir datos sensibles identificables de vista previa compartida.
- **Precondiciones:** conversación o preparación de caso.
- **Flujo principal:** orientar a reportar estados sin revelar credenciales; no repetir datos sensibles innecesariamente.
- **Alternativas y errores:** política de eliminación de secreto enviado por usuario aún pendiente; no incorporarlo a caso compartido.
- **Resultado:** exposición minimizada.
- **Aceptación:** asistente no pregunta credenciales; vista previa omite secretos; respuesta/log no los repite innecesariamente.

### Módulo 12. Errores y situaciones excepcionales

#### RF-044 — Pérdida de conexión e interrupción
- **Módulo/prioridad/actor:** 12 / Alta / usuario y sistema.
- **Descripción:** distinguir borrador de mensaje enviado, indicar pérdida de conexión y permitir reintento sin duplicar turno confirmado.
- **Precondiciones:** operación en curso.
- **Flujo principal:** detectar falta de confirmación; conservar borrador en vista activa; reintentar o verificar estado al reconectar.
- **Alternativas y errores:** si estado remoto es incierto, informarlo y no afirmar éxito.
- **Resultado:** usuario sabe si debe reintentar.
- **Aceptación:** no confirmado no se marca enviado; reintento no duplica respuesta guardada; borrador sigue visible en vista activa.

#### RF-045 — Error o timeout de IA
- **Módulo/prioridad/actor:** 12 / Alta / sistema.
- **Descripción:** gestionar indisponibilidad, límite o timeout del modelo sin mostrar error interno ni inventar respuesta.
- **Precondiciones:** consulta IA en curso.
- **Flujo principal:** informar que no pudo analizar; ofrecer reintento; conservar estado guardado conforme a política.
- **Alternativas y errores:** si se desconoce si proveedor procesó, evitar reenvío automático de fotos y declarar estado incierto.
- **Resultado:** fallo visible y recuperable.
- **Aceptación:** error no aparece como diagnóstico; hay opción de reintento; no se filtran secretos.

#### RF-046 — Error de carga o archivo rechazado
- **Módulo/prioridad/actor:** 12 / Alta / instalador.
- **Descripción:** identificar archivo fallido y motivo; conservar descripción y adjuntos válidos cuando sea seguro.
- **Precondiciones:** mensaje con foto.
- **Flujo principal:** informar fallo de carga/validación; permitir quitar o reemplazar.
- **Alternativas y errores:** no iniciar análisis como si foto fallida estuviera adjunta.
- **Resultado:** mensaje corregible.
- **Aceptación:** error identifica razón; descripción permanece en borrador; respuesta no afirma haber analizado foto fallida.

#### RF-047 — Error al guardar datos o consentimiento
- **Módulo/prioridad/actor:** 12 / Crítica / sistema.
- **Descripción:** declarar guardado solo cuando servicio lo confirma; permitir reintento seguro.
- **Precondiciones:** escritura de mensaje, resultado o permiso.
- **Flujo principal:** persistir; reflejar éxito confirmado.
- **Alternativas y errores:** error en confirmación/permiso mantiene caso privado y estado anterior.
- **Resultado:** interfaz no informa falso éxito.
- **Aceptación:** falla de guardar autorización impide compartir; falla de confirmación no marca éxito; se informa estado/reintento.

#### RF-048 — Sesión expirada durante operación
- **Módulo/prioridad/actor:** 12 / Crítica / instalador autenticado.
- **Descripción:** detener operaciones privadas ante sesión vencida y exigir nueva autenticación.
- **Precondiciones:** expiración durante carga, consulta o guardado.
- **Flujo principal:** detectar rechazo; bloquear historial/acciones privadas; pedir iniciar sesión.
- **Alternativas y errores:** no reejecutar automáticamente operación sensible tras reautenticación.
- **Resultado:** no hay acción privada sin sesión.
- **Aceptación:** historial no se recupera con sesión vencida; permiso no se registra si sesión caducó; reautenticación requerida.

#### RF-049 — Respuesta vacía o no utilizable
- **Módulo/prioridad/actor:** 12 / Alta / sistema y asistente.
- **Descripción:** detectar salida vacía y mostrar error/reintento en lugar de fabricar contenido.
- **Precondiciones:** proveedor respondió.
- **Flujo principal:** validar existencia de contenido útil antes de presentarlo como respuesta.
- **Alternativas y errores:** incertidumbre del modelo se conserva; no se sustituye por diagnóstico supuesto.
- **Resultado:** usuario no confunde salida vacía con solución.
- **Aceptación:** salida vacía da aviso y opción de reintento; no crea solución ficticia; contexto guardado permanece consultable.

#### RF-050 — Equipo o procedimiento no validable
- **Módulo/prioridad/actor:** 12 / Crítica / asistente.
- **Descripción:** si falta modelo, documentación o validación necesaria, reconocerlo y no emitir instrucciones específicas; pedir dato, consultar manual oficial o escalar.
- **Precondiciones:** recomendación depende de dato no verificado.
- **Flujo principal:** explicar límite y requerimiento concreto.
- **Alternativas y errores:** solo ofrecer comprobación general segura/reversible que no dependa del dato.
- **Resultado:** sin procedimiento inventado o incompatible.
- **Aceptación:** modelo no se adivina; procedimiento desconocido no se completa por conjetura; límite y camino alternativo se muestran.

## 4. Requisitos no funcionales

Los valores numéricos propuestos requieren validación; no son compromisos de servicio aprobados.

#### NFR-001 — Transporte y sesión
- **Prioridad:** Crítica. **Verificación:** inspección de configuración y pruebas.
- Comunicación publicada navegador-backend por HTTPS; toda operación privada exige sesión válida y autorización servidor.
- **Aceptación:** solicitudes privadas sin sesión/vencidas son denegadas; credenciales de modelo no aparecen en cliente.

#### NFR-002 — Aislamiento y RLS
- **Prioridad:** Crítica. **Verificación:** pruebas con dos usuarios y revisión de políticas.
- Acceso por propietario en memoria/conversaciones/fotos; conocimiento limitado a casos autorizados vigentes.
- **Aceptación:** pruebas cruzadas de lectura/escritura fallan de forma segura; RLS y backend cubren operaciones aprobadas.

#### NFR-003 — Privacidad y minimización
- **Prioridad:** Crítica. **Verificación:** revisión de datos, logs y vistas de compartir.
- Solicitar y retener solo lo necesario; compartir representación depurada, no conversación completa.
- **Aceptación:** vista compartible omite datos no autorizados; logs no muestran credenciales ni imágenes.

#### NFR-004 — Protección de secretos
- **Prioridad:** Crítica. **Verificación:** inspección de frontend, artefacto y repositorio.
- Secretos OpenAI solo en backend/configuración segura; no en frontend, control de versiones, logs ni errores.
- **Aceptación:** artefacto cliente no contiene credenciales; error externo no las revela.

#### NFR-005 — Seguridad de archivos
- **Prioridad:** Crítica. **Verificación:** pruebas de tipo, peso, corrupción y acceso.
- Validar del lado servidor y mantener imágenes privadas.
- **Aceptación:** archivo falsificado/sobredimensionado y acceso de otra cuenta se rechazan.

#### NFR-006 — Rendimiento de interfaz
- **Prioridad:** Alta. **Verificación:** medición con entorno documentado.
- **Objetivo propuesto:** percentil 95 de render de chat con hasta 100 mensajes en no más de 2 segundos, excluyendo servicios externos; validar en pruebas antes de adoptarlo.
- **Aceptación:** informe registra dispositivo, navegador, red, tamaño y percentiles; desviaciones se documentan.

#### NFR-007 — Latencia de IA
- **Prioridad:** Media. **Verificación:** medición integrada.
- Timeout configurable; no se fija SLA ni latencia total antes de evaluar proveedor/modelo.
- **Aceptación:** timeout informa error recuperable, registra métrica sin contenido privado y no deja indicador infinito.

#### NFR-008 — Disponibilidad y degradación
- **Prioridad:** Alta. **Verificación:** simulación de fallo de servicios.
- Informar fallos de auth, storage, base de datos e IA; no corromper estado ni declarar publicación/guardado no confirmado. Porcentaje de disponibilidad queda pendiente de alojamiento.
- **Aceptación:** fallo simulado produce estado comprensible y no falso éxito.

#### NFR-009 — Usabilidad
- **Prioridad:** Alta. **Verificación:** pruebas observadas con instaladores.
- Acciones etiquetadas sencillamente; mensajes indican qué puede hacer el usuario; no requieren jerga informática.
- **Aceptación:** participantes pueden autenticarse, enviar texto/foto y abrir historial con instrucciones mínimas; hallazgos quedan registrados.

#### NFR-010 — Accesibilidad
- **Prioridad:** Alta. **Verificación:** teclado y lector de pantalla en flujos principales.
- Campos, botones, mensajes de estado y errores con nombre accesible, foco visible y señales que no dependan solo del color.
- **Aceptación:** flujos principales se completan por teclado; estados/error se identifican accesiblemente.

#### NFR-011 — Adaptabilidad y navegadores
- **Prioridad:** Alta. **Verificación:** matriz de navegadores/dispositivos acordada.
- Interfaz utilizable en computador, tableta y celular; versiones modernas de navegadores se acuerdan antes de aceptación.
- **Aceptación:** flujo principal se completa en cada combinación acordada sin controles inaccesibles; matriz queda registrada.

#### NFR-012 — Mantenibilidad
- **Prioridad:** Alta. **Verificación:** revisión por desarrollador no autor.
- Mantener responsabilidades modulares conforme al monolito aprobado y documentación comprensible; no fija bibliotecas adicionales.
- **Aceptación:** se localizan módulos conversacionales, media, IA, memoria y conocimiento a partir de documentación del proyecto.

#### NFR-013 — Registro operativo
- **Prioridad:** Alta. **Verificación:** revisión de logs ante errores simulados.
- Registrar tipo de error/estado mínimo sin duplicar mensajes, fotos, credenciales o tokens.
- **Aceptación:** fallos de auth, carga, persistencia e IA son distinguibles; logs de prueba no contienen contenido sensible.

#### NFR-014 — Calidad y límites de IA
- **Prioridad:** Crítica. **Verificación:** conjunto de escenarios revisado antes de publicación.
- Evaluar coloquialismos, faltas, fotos claras/ilegibles, preguntas, incertidumbre, seguridad, no repetición y seis resultados del seguimiento.
- **Aceptación:** cada escenario tiene respuesta esperada y revisión; no se aprueba si inventa modelo/procedimiento, comparte sin permiso o marca parcial/temporal como resuelto.

## 5. Reglas de negocio

| Código | Regla |
|---|---|
| RN-001 | Cada instalador accede solo a sus datos privados. |
| RN-002 | Memoria individual y conocimiento compartido están separados; no hay publicación automática. |
| RN-003 | Texto de caso se comparte solo con confirmación positiva completa y autorización expresa vigente. |
| RN-004 | Confirmación no equivale a consentimiento; silencio nunca autoriza. |
| RN-005 | Fotografía requiere autorización independiente. |
| RN-006 | Mejoría parcial o temporal no es solución confirmada. |
| RN-007 | No probado no significa éxito ni fallo. |
| RN-008 | Respuesta ambigua requiere aclaración y no cierra caso. |
| RN-009 | Observación, hipótesis y diagnóstico confirmado se distinguen. |
| RN-010 | No se inventan marca, modelo, especificación, procedimiento ni dato faltante. |
| RN-011 | Solo se recupera contexto pertinente del instalador autenticado. |
| RN-012 | Problemas independientes mantienen equipos, pasos y resultados separados. |
| RN-013 | Pasos intentados y resultados se conservan para evitar repetición. |
| RN-014 | Casos compartidos son experiencias contextuales, no garantía universal. |
| RN-015 | No se solicitan contraseñas, claves WiFi, tokens ni credenciales privadas. |
| RN-016 | Acción de alto impacto exige advertencia, documentación/compatibilidad, respaldo/recuperación y aceptación; si no se valida, no se guía. |
| RN-017 | Fotografías son privadas por defecto. |
| RN-018 | Rechazo o falta de respuesta mantiene privado el recurso. |
| RN-019 | Revocación retira de futuras consultas; no afirmar borrado de copias/backups sin verificarlo. |
| RN-020 | Error al guardar confirmación/permiso impide cambiar estado o compartir como exitoso. |
| RN-021 | Catálogo comercial, ventas, compras y precios quedan fuera del MVP. El inventario para reparaciones (existencias, equipos instalados, reparaciones) se autorizó el 2026-11-19. |

## 6. Flujos funcionales obligatorios

Los flujos especifican comportamiento observable, no endpoints ni secuencia interna de API.

1. **Registro e inicio de sesión:** visitante registra cuenta → servicio valida → sistema informa alta/verificación → usuario inicia sesión → sistema abre espacio privado. Credenciales incorrectas o servicio caído no revelan cuentas.
2. **Iniciar conversación técnica:** usuario autenticado selecciona nueva conversación → sistema crea contexto separado → muestra entrada vacía.
3. **Enviar problema con texto:** usuario describe síntoma → sistema muestra procesamiento → interpreta lenguaje/contexto → devuelve pregunta o respuesta estructurada.
4. **Enviar problema con fotografía:** usuario adjunta foto dentro de límites → sistema valida/asocia/almacena en privado → analiza texto e imagen → comunica observaciones y límites.
5. **Falta información:** asistente detecta dato que cambia paso → pregunta → usuario responde → contexto se actualiza y no repite pregunta.
6. **Equipo no identificado:** asistente reconoce límite → solicita modelo o foto enfocada → si continúa desconocido no da procedimiento dependiente de modelo y escala.
7. **Recomendación segura:** asistente señala hipótesis → da paso, revisión y resultado esperado → espera respuesta → interpreta sin declarar certeza indebida.
8. **Solución funciona:** instalador confirma resolución completa → sistema registra en privado → ofrece consentimiento textual separado → no comparte hasta autorización.
9. **Mejora parcial:** sistema registra qué mejoró y qué persiste → mantiene abierto → pregunta o propone siguiente paso seguro.
10. **Solución temporal:** registra duración/recurrencia → mantiene abierto → retoma diagnóstico.
11. **No funciona:** registra fallo → no repite el paso como nuevo → actualiza hipótesis, pregunta, ofrece alternativa o escala.
12. **Consultar historial:** usuario abre lista → ve solo sus conversaciones/fechas → selecciona una → historial aparece ordenado.
13. **Recuperar memoria:** sistema identifica contexto pertinente del usuario → recupera lo mínimo → confirma datos dudosos antes de asumir.
14. **Registrar caso confirmado:** confirmación completa → sistema conserva síntoma, equipo/contexto, procedimiento, resultados, solución reportada, límites y desconocidos → sigue privado.
15. **Autorizar texto:** sistema presenta versión depurada → instalador autoriza expresamente → sistema registra → incorpora solo texto autorizado si confirmación es positiva.
16. **Autorizar fotografía:** sistema identifica imágenes candidatas → usuario selecciona/autoriza separadamente → solo esas imágenes pueden ser referencias del caso elegible.
17. **Rechazar autorización:** usuario rechaza o no decide → texto/fotos permanecen privados y conversación individual continúa.
18. **Revocar autorización:** usuario revoca texto o imagen → sistema bloquea nuevas consultas compartidas de ese recurso → informa estado y cualquier eliminación física pendiente.
19. **Consultar conocimiento compartido:** sistema recupera solo casos autorizados vigentes → compara problema/equipo → explica semejanzas, diferencias y procedencia no personal.
20. **Escalar por riesgo o falta de evidencia:** sistema detecta riesgo/procedimiento no validado → detiene instrucciones → explica límite → recomienda manual oficial o personal calificado.

## 7. Priorización y trazabilidad

### Matriz de requisitos por módulo

| Módulo | Requisitos | Prioridad de entrega |
|---|---|---|
| 1. Usuarios/autenticación | RF-001–005 | Crítica/alta; recuperación condicionada al proveedor |
| 2. Interfaz/conversación | RF-006–010 | Alta/crítica |
| 3. Fotografías | RF-011–015 | Alta/crítica |
| 4. Diagnóstico | RF-016–020 | Alta/crítica |
| 5. Recomendaciones | RF-021–023 | Alta/crítica |
| 6. Seguimiento | RF-024–026 | Crítica/alta |
| 7. Historial | RF-027–029 | Alta |
| 8. Memoria | RF-030–032 | Alta/crítica |
| 9. Registro de casos | RF-033–035 | Alta/crítica |
| 10. Conocimiento compartido | RF-036–039 | Alta/crítica |
| 11. Privacidad/consentimiento | RF-040–043 | Crítica |
| 12. Errores/excepciones | RF-044–050 | Alta/crítica |

### Trazabilidad de reglas y dependencias

| Requisitos | Reglas principales |
|---|---|
| RF-004, RF-015, RF-028, RF-032, RF-040–043 | RN-001, RN-002, RN-005, RN-011, RN-017–019 |
| RF-016–020, RF-050 | RN-009–012 |
| RF-021–023 | RN-010, RN-015–016 |
| RF-024–026 | RN-006–008, RN-013 |
| RF-033–039 | RN-003–005, RN-014, RN-018–020 |
| RF-044–049 | RN-020 |
| Alcance general | RN-021 |

- Autenticación (RF-001–005) precede a historial, memoria, fotos y chat privado.
- Persistencia de mensajes/resultados precede a historial, memoria y casos.
- Modelo multimodal final condiciona formatos y límites de RF-011–014.
- Confirmación y consentimiento textual son condiciones independientes para RF-036–039; el permiso de foto es independiente.
- Backend y RLS deben probarse antes de publicar datos privados/compartidos.
- Búsqueda debe filtrar permisos y revocaciones antes de evaluar relevancia.

### Dependencias externas aprobadas/candidatas

- **Supabase Auth:** autenticación; alternativa principal a evaluar, configuración pendiente.
- **PostgreSQL mediante Supabase:** conversaciones, estados, memoria y casos.
- **Supabase Storage privado:** fotografías.
- **OpenAI API:** primer proveedor multimodal a evaluar, no elección definitiva; credenciales solo backend.
- **API REST sobre HTTPS:** React + TypeScript con Python + FastAPI.

Este documento no define contratos API, tablas, migraciones ni diseño físico; requieren documentación y aprobación separadas.

## 8. Fuera del alcance del MVP

No se incluyen catálogo comercial, inventario de cámaras/DVR/NVR/accesorios, cantidades, existencias, precios, cotizaciones, pedidos, compras, ventas, proveedores ni conexión con inventarios externos. Ningún requisito de este documento habilita estas funciones. El chatbot debe mantener responsabilidades modulares y no depender de un catálogo o inventario para operar; una integración futura requerirá alcance y autorización propios, sin diseñar aquí ese módulo.

> **Actualización 2026-11-19:** el inventario para reparaciones se diseñó como módulo propio; el chatbot solo lo consulta mediante herramientas de lectura y sigue funcionando si el inventario no está disponible. Ver [inventario-y-asistente.md](../architecture/inventario-y-asistente.md).

## 9. Decisiones pendientes

Las recomendaciones son propuestas, no decisiones aprobadas.

| Decisión | Por qué / impacto | ¿Bloquea inicio? | Alternativa recomendada | Hito |
|---|---|---|---|---|
| Modelo multimodal definitivo | Afecta calidad, límites de fotos, privacidad, costo y latencia. | Bloquea integración/pruebas con proveedor, no UI. | Evaluar OpenAI primero con casos de texto/imagen y comparar costo, calidad y privacidad. | Antes de integrar IA y pruebas de aceptación. |
| Método final de Supabase Auth y recuperación | Afecta RF-001–005. | Bloquea autenticación real, no diseño. | Evaluar flujos disponibles y escoger configuración antes de implementar. | Antes del módulo de usuarios. |
| Matriz de permisos y RLS | Afecta datos privados y compartidos. | Bloquea acceso a datos reales/publicación. | Definir matriz por recurso; probar RLS junto a autorización backend. | Antes de persistencia y despliegue. |
| Formatos/tamaño/cantidad de fotos | Afecta RF-011–014 y proveedor. | No bloquea diseño; sí aceptación de carga. | Validar JPEG/PNG/WebP, 3 fotos y 10 MB por foto como propuesta inicial. | Prototipo de carga, antes de cerrar pruebas. |
| Consentimiento y vista depurada | Afecta RF-034, RF-036–038, RF-041–042. | Bloquea compartir; no chat privado. | Permisos afirmativos y separados; mostrar exactamente qué se publica. | Antes de habilitar conocimiento compartido. |
| Revocación y copias/backups | Afecta RF-039/RF-042. | Bloquea promesa de borrado total; se puede bloquear acceso compartido. | Retirar inmediatamente de búsquedas; definir eliminación de objetos/derivados/backups y comunicar límites. | Antes de pedir consentimiento en producción. |
| Retención de chats, fotos y memoria | Afecta RF-025, RF-030–035. | Bloquea política de operación en producción. | Definir mínimo necesario y efecto de solicitudes de eliminación; no asumir plazo hoy. | Antes de producción. |
| Búsqueda y criterio de aplicabilidad | Afecta RF-038. | Bloquea calidad de búsqueda compartida, no chat base. | Empezar con filtros y texto; evaluar semántica solo si se requiere y aprueba. | Antes de activar consulta compartida. |
| Objetivos de rendimiento/disponibilidad | Afecta NFR-006–008. | No bloquea inicio; sí aceptación operativa final. | Medir objetivo UI propuesto y fijar disponibilidad tras elegir hosting. | Pruebas/antes de publicar. |
| Navegadores y accesibilidad | Afecta NFR-009–011. | No bloquea diseño; bloquea aceptación completa. | Definir matriz de uso y validar teclado/lector. | Antes de aceptación. |
| Evidencia de seguridad para acciones destructivas | Afecta RF-023/NFR-014. | Bloquea guiar reset, no comprobaciones seguras. | Exigir modelo/manual, respaldo, recuperación y aceptación; si no, escalar. | Antes de habilitar acción de impacto. |

## 10. Auditoría de consistencia y cobertura

- **Módulos:** están documentados los 12 solicitados.
- **Requisitos funcionales:** RF-001 a RF-050, códigos únicos y continuos.
- **Criterios de aceptación:** los 50 RF incluyen criterios observables.
- **Reglas de negocio:** RN-001 a RN-021.
- **Flujos:** los 20 obligatorios están documentados paso a paso.
- **Resultados:** parcial, temporal, fallido, no probado y ambiguo no se confunden con resolución confirmada.
- **Compartir:** texto exige confirmación positiva y autorización expresa; foto tiene autorización independiente; silencio/rechazo mantienen privacidad.
- **Revocación:** se retira de consultas compartidas; no se afirma borrar copias/backups sin verificarlo; política queda pendiente.
- **Problemas distintos:** equipos, acciones y resultados no se mezclan sin confirmar relación.
- **Riesgo:** factory reset y cambios de impacto requieren aviso, equipo/documentación, respaldo/recuperación y aceptación; si no se valida, no se guía.
- **Tecnología:** mantiene React + TypeScript, Python + FastAPI, REST/HTTPS, PostgreSQL/Supabase, Storage privado, Supabase Auth como alternativa principal a evaluar y OpenAI como candidato inicial.
- **Inventario:** excluido en la versión original; el inventario para reparaciones se autorizó el 2026-11-19 (ver `docs/architecture/inventario-y-asistente.md`). Lo comercial sigue excluido.
- **Diferencias documentales:** no se encontró conflicto material entre AGENTS.md y los documentos de arquitectura. Candidatos y pendientes se mantienen expresamente como tales.
- **No se define:** endpoints, contratos, esquema físico, migraciones ni políticas de retención aún no aprobadas.

La aprobación de este documento no inicia implementación ni aprueba automáticamente decisiones pendientes.

