-- =====================================================================
--  PedidoCentral - Base de datos MySQL
--  Sistema de Centralizacion y Seguimiento de Pedidos Multicanal
--  para Cocinas Ocultas (El Cairo)
--
--  Integrantes: Luis Alandete, Santiago Angulo, Fabian Hernandez
--  Base: documento "PedidoCentral_Clase_4" (RF-01..RF-05, RNF-01/02,
--        NEC-01..NEC-03, modulos M1..M7, clases criticas y decisiones DT)
--
--  Motor recomendado: MySQL 8.0+ (usa CHECK, triggers y procedimientos).
--  Uso:  mysql -u root -p < pedidocentral.sql
-- =====================================================================

DROP DATABASE IF EXISTS pedidocentral;
CREATE DATABASE pedidocentral
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;
USE pedidocentral;

-- =====================================================================
-- 1. TABLAS
--    Las columnas conservan los nombres del diagrama de clases (7.3).
-- =====================================================================

-- ---- M7 Administracion y Seguridad (DT-08: acceso por roles) --------
CREATE TABLE rol (
  idRol        TINYINT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre       VARCHAR(30)  NOT NULL,
  descripcion  VARCHAR(150) NULL,
  PRIMARY KEY (idRol),
  UNIQUE KEY uq_rol_nombre (nombre)
) ENGINE=InnoDB;

CREATE TABLE usuario (
  idUsuario     INT UNSIGNED NOT NULL AUTO_INCREMENT,
  idRol         TINYINT UNSIGNED NOT NULL,
  nombre        VARCHAR(100) NOT NULL,
  telefono      VARCHAR(20)  NULL,
  username      VARCHAR(40)  NOT NULL,
  passwordHash  VARCHAR(255) NOT NULL,           -- nunca guardar la clave en texto plano
  activo        TINYINT(1)   NOT NULL DEFAULT 1,
  PRIMARY KEY (idUsuario),
  UNIQUE KEY uq_usuario_username (username),
  KEY idx_usuario_rol (idRol),
  CONSTRAINT fk_usuario_rol FOREIGN KEY (idRol) REFERENCES rol (idRol)
) ENGINE=InnoDB;

-- ---- M6 Clientes (NEC-01: evitar pedidos duplicados por telefono) ---
CREATE TABLE cliente (
  idCliente      INT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre         VARCHAR(100) NOT NULL,
  telefono       VARCHAR(20)  NOT NULL,
  direccion      VARCHAR(200) NOT NULL,
  fechaRegistro  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (idCliente),
  UNIQUE KEY uq_cliente_telefono (telefono)      -- buscarPorTelefono() (R-04)
) ENGINE=InnoDB;

-- ---- M1 / M3 Pedido (asociacion 1:N con Cliente) --------------------
CREATE TABLE pedido (
  idPedido          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  idCliente         INT UNSIGNED NOT NULL,
  idUsuarioCajera   INT UNSIGNED NOT NULL,       -- quien registra el pedido en el POS
  canal             ENUM('WhatsApp','Instagram') NOT NULL,
  fechaHora         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  estado            ENUM('Registrado','En Cocina','En Ruta','Entregado')
                    NOT NULL DEFAULT 'Registrado',                -- RF-05
  total             DECIMAL(10,2) NOT NULL DEFAULT 0,
  direccionEntrega  VARCHAR(200) NOT NULL,
  observaciones     VARCHAR(300) NULL,                            -- RF-01
  PRIMARY KEY (idPedido),
  KEY idx_pedido_estado (estado),
  KEY idx_pedido_fecha (fechaHora),
  KEY idx_pedido_cliente (idCliente),
  KEY idx_pedido_cajera (idUsuarioCajera),
  CONSTRAINT ck_pedido_total CHECK (total >= 0),
  CONSTRAINT fk_pedido_cliente FOREIGN KEY (idCliente) REFERENCES cliente (idCliente),
  CONSTRAINT fk_pedido_cajera  FOREIGN KEY (idUsuarioCajera) REFERENCES usuario (idUsuario)
) ENGINE=InnoDB;

-- ---- DetallePedido (composicion 1:N con Pedido) ---------------------
CREATE TABLE detalle_pedido (
  idDetalle  INT UNSIGNED NOT NULL AUTO_INCREMENT,
  idPedido   INT UNSIGNED NOT NULL,
  producto   VARCHAR(100) NOT NULL,
  cantidad   SMALLINT UNSIGNED NOT NULL,
  subtotal   DECIMAL(10,2) NOT NULL,
  PRIMARY KEY (idDetalle),
  KEY idx_detalle_pedido (idPedido),
  CONSTRAINT ck_detalle_cantidad CHECK (cantidad > 0),
  CONSTRAINT ck_detalle_subtotal CHECK (subtotal >= 0),
  -- composicion: el detalle no existe sin el pedido
  CONSTRAINT fk_detalle_pedido FOREIGN KEY (idPedido) REFERENCES pedido (idPedido)
    ON DELETE CASCADE
) ENGINE=InnoDB;

-- ---- M2 Pago (vinculo 1:1 con Pedido, RF-03 / NEC-03) ---------------
CREATE TABLE pago (
  idPago           INT UNSIGNED NOT NULL AUTO_INCREMENT,
  idPedido         INT UNSIGNED NOT NULL,
  medioPago        VARCHAR(30)  NOT NULL,
  urlComprobante   VARCHAR(500) NULL,            -- el archivo vive fuera de la BD (DT-05)
  validado         TINYINT(1)   NOT NULL DEFAULT 0,
  idUsuarioValida  INT UNSIGNED NULL,            -- quien valido (mitiga R-05)
  fechaValidacion  DATETIME     NULL,
  fechaRegistro    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (idPago),
  UNIQUE KEY uq_pago_pedido (idPedido),          -- 1 a 1
  KEY idx_pago_valida (idUsuarioValida),
  -- un pago solo puede quedar validado si tiene comprobante y responsable
  CONSTRAINT ck_pago_validado CHECK (
    validado = 0 OR (urlComprobante IS NOT NULL AND idUsuarioValida IS NOT NULL)
  ),
  CONSTRAINT fk_pago_pedido  FOREIGN KEY (idPedido) REFERENCES pedido (idPedido),
  CONSTRAINT fk_pago_usuario FOREIGN KEY (idUsuarioValida) REFERENCES usuario (idUsuario)
) ENGINE=InnoDB;

-- ---- M4 ComandaKDS (1:1 con Pedido, RF-02 / RF-04) ------------------
CREATE TABLE comanda_kds (
  idComanda          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  idPedido           INT UNSIGNED NOT NULL,
  estadoPreparacion  ENUM('Pendiente','Listo') NOT NULL DEFAULT 'Pendiente',
  alertaTiempo       TINYINT(1)   NOT NULL DEFAULT 0,   -- 1 = supero 20 minutos (rojo)
  fechaInicio        DATETIME     NULL,                 -- arranca iniciarTimer()
  fechaListo         DATETIME     NULL,
  PRIMARY KEY (idComanda),
  UNIQUE KEY uq_comanda_pedido (idPedido),              -- 1 a 1
  KEY idx_comanda_estado (estadoPreparacion),
  CONSTRAINT fk_comanda_pedido FOREIGN KEY (idPedido) REFERENCES pedido (idPedido)
) ENGINE=InnoDB;

-- ---- M5 Despacho (CU-05: En Ruta -> Entregado) ----------------------
CREATE TABLE despacho (
  idDespacho         INT UNSIGNED NOT NULL AUTO_INCREMENT,
  idPedido           INT UNSIGNED NOT NULL,
  idDomiciliario     INT UNSIGNED NOT NULL,
  fechaAsignacion    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fechaNotificacion  DATETIME NULL,              -- notificarDomiciliario()
  fechaSalida        DATETIME NULL,              -- pasa a En Ruta
  fechaEntrega       DATETIME NULL,              -- pasa a Entregado
  PRIMARY KEY (idDespacho),
  UNIQUE KEY uq_despacho_pedido (idPedido),
  KEY idx_despacho_domiciliario (idDomiciliario),
  CONSTRAINT fk_despacho_pedido FOREIGN KEY (idPedido) REFERENCES pedido (idPedido),
  CONSTRAINT fk_despacho_domiciliario FOREIGN KEY (idDomiciliario) REFERENCES usuario (idUsuario)
) ENGINE=InnoDB;

-- ---- Trazabilidad completa (RF-05) ----------------------------------
CREATE TABLE historial_estado_pedido (
  idHistorial    INT UNSIGNED NOT NULL AUTO_INCREMENT,
  idPedido       INT UNSIGNED NOT NULL,
  estadoAnterior ENUM('Registrado','En Cocina','En Ruta','Entregado') NULL,
  estadoNuevo    ENUM('Registrado','En Cocina','En Ruta','Entregado') NOT NULL,
  fechaHora      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  idUsuario      INT UNSIGNED NULL,
  PRIMARY KEY (idHistorial),
  KEY idx_hist_pedido (idPedido, fechaHora),
  CONSTRAINT fk_hist_pedido  FOREIGN KEY (idPedido) REFERENCES pedido (idPedido) ON DELETE CASCADE,
  CONSTRAINT fk_hist_usuario FOREIGN KEY (idUsuario) REFERENCES usuario (idUsuario)
) ENGINE=InnoDB;

-- =====================================================================
-- 2. TRIGGERS (reglas de negocio que no deben depender de la pantalla)
-- =====================================================================
DELIMITER $$

-- Al registrar un pedido se guarda el primer estado en el historial.
CREATE TRIGGER trg_pedido_ai
AFTER INSERT ON pedido
FOR EACH ROW
BEGIN
  INSERT INTO historial_estado_pedido (idPedido, estadoAnterior, estadoNuevo, idUsuario)
  VALUES (NEW.idPedido, NULL, NEW.estado, NEW.idUsuarioCajera);
END$$

-- RF-05 (estados en orden) y RF-03 (sin comprobante validado no pasa a cocina).
CREATE TRIGGER trg_pedido_bu
BEFORE UPDATE ON pedido
FOR EACH ROW
BEGIN
  IF NEW.estado <> OLD.estado THEN
    IF NOT (   (OLD.estado = 'Registrado' AND NEW.estado = 'En Cocina')
            OR (OLD.estado = 'En Cocina'  AND NEW.estado = 'En Ruta')
            OR (OLD.estado = 'En Ruta'    AND NEW.estado = 'Entregado')) THEN
      SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'RF-05: transicion de estado no valida';
    END IF;

    IF NEW.estado = 'En Cocina' THEN
      IF NOT EXISTS (SELECT 1 FROM pago
                      WHERE idPedido = OLD.idPedido
                        AND validado = 1
                        AND urlComprobante IS NOT NULL) THEN
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT = 'RF-03: el pago debe tener comprobante validado antes de pasar a cocina';
      END IF;
    END IF;

    IF NEW.estado = 'En Ruta' THEN
      IF NOT EXISTS (SELECT 1 FROM comanda_kds
                      WHERE idPedido = OLD.idPedido
                        AND estadoPreparacion = 'Listo') THEN
        SIGNAL SQLSTATE '45000'
          SET MESSAGE_TEXT = 'CU-04: cocina debe marcar el pedido como Listo antes de salir En Ruta';
      END IF;
    END IF;
  END IF;
END$$

-- Cada cambio de estado queda registrado (trazabilidad).
CREATE TRIGGER trg_pedido_au
AFTER UPDATE ON pedido
FOR EACH ROW
BEGIN
  IF NEW.estado <> OLD.estado THEN
    INSERT INTO historial_estado_pedido (idPedido, estadoAnterior, estadoNuevo, idUsuario)
    VALUES (NEW.idPedido, OLD.estado, NEW.estado, @idUsuarioActual);
  END IF;
END$$

-- El total del pedido siempre es la suma de sus detalles.
CREATE TRIGGER trg_detalle_ai
AFTER INSERT ON detalle_pedido
FOR EACH ROW
BEGIN
  UPDATE pedido
     SET total = (SELECT COALESCE(SUM(subtotal), 0) FROM detalle_pedido WHERE idPedido = NEW.idPedido)
   WHERE idPedido = NEW.idPedido;
END$$

CREATE TRIGGER trg_detalle_au
AFTER UPDATE ON detalle_pedido
FOR EACH ROW
BEGIN
  UPDATE pedido
     SET total = (SELECT COALESCE(SUM(subtotal), 0) FROM detalle_pedido WHERE idPedido = NEW.idPedido)
   WHERE idPedido = NEW.idPedido;
END$$

CREATE TRIGGER trg_detalle_ad
AFTER DELETE ON detalle_pedido
FOR EACH ROW
BEGIN
  UPDATE pedido
     SET total = (SELECT COALESCE(SUM(subtotal), 0) FROM detalle_pedido WHERE idPedido = OLD.idPedido)
   WHERE idPedido = OLD.idPedido;
END$$

-- El despacho solo se crea si el rol del usuario es Domiciliario.
CREATE TRIGGER trg_despacho_bi
BEFORE INSERT ON despacho
FOR EACH ROW
BEGIN
  IF NOT EXISTS (SELECT 1
                   FROM usuario u JOIN rol r ON r.idRol = u.idRol
                  WHERE u.idUsuario = NEW.idDomiciliario
                    AND r.nombre = 'Domiciliario'
                    AND u.activo = 1) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'El usuario asignado no es un domiciliario activo';
  END IF;
END$$

-- =====================================================================
-- 3. PROCEDIMIENTOS ALMACENADOS (flujo del diagrama de secuencia 7.4)
-- =====================================================================

-- CU-02: la cajera (o el administrador) valida el comprobante.
CREATE PROCEDURE sp_validar_pago(IN p_idPago INT UNSIGNED, IN p_idUsuario INT UNSIGNED)
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pago WHERE idPago = p_idPago AND urlComprobante IS NOT NULL) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'RF-03: el pago no tiene comprobante adjunto';
  END IF;

  UPDATE pago
     SET validado = 1,
         idUsuarioValida = p_idUsuario,
         fechaValidacion = NOW()
   WHERE idPago = p_idPago;
END$$

-- ComandaKDS.iniciarTimer(): arranca el temporizador de 20 minutos (RF-04).
CREATE PROCEDURE sp_iniciar_timer(IN p_idComanda INT UNSIGNED)
BEGIN
  UPDATE comanda_kds
     SET fechaInicio = NOW(),
         alertaTiempo = 0
   WHERE idComanda = p_idComanda;
END$$

-- Controlador.crearPedido() -> publicarNuevaComanda(): envia el pedido a cocina (RF-02).
CREATE PROCEDURE sp_enviar_a_cocina(IN p_idPedido INT UNSIGNED, IN p_idUsuario INT UNSIGNED)
BEGIN
  DECLARE v_estado VARCHAR(20);
  DECLARE v_idComanda INT UNSIGNED;
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  SELECT estado INTO v_estado FROM pedido WHERE idPedido = p_idPedido;
  IF v_estado IS NULL OR v_estado <> 'Registrado' THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Solo se puede enviar a cocina un pedido en estado Registrado';
  END IF;

  START TRANSACTION;
    SET @idUsuarioActual = p_idUsuario;
    UPDATE pedido SET estado = 'En Cocina' WHERE idPedido = p_idPedido;   -- valida RF-03 (trigger)
    INSERT INTO comanda_kds (idPedido) VALUES (p_idPedido);
    SET v_idComanda = LAST_INSERT_ID();
    CALL sp_iniciar_timer(v_idComanda);
  COMMIT;
END$$

-- CU-04: el cocinero presiona "Listo".
CREATE PROCEDURE sp_marcar_listo(IN p_idComanda INT UNSIGNED)
BEGIN
  UPDATE comanda_kds
     SET estadoPreparacion = 'Listo',
         fechaListo = NOW(),
         alertaTiempo = IF(TIMESTAMPDIFF(SECOND, fechaInicio, NOW()) > 1200, 1, 0)
   WHERE idComanda = p_idComanda
     AND estadoPreparacion = 'Pendiente';

  IF ROW_COUNT() = 0 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'La comanda no existe o ya estaba marcada como Listo';
  END IF;
END$$

-- RF-04: marca en rojo las comandas pendientes que superan 20 minutos.
CREATE PROCEDURE sp_actualizar_alertas_tiempo()
BEGIN
  UPDATE comanda_kds
     SET alertaTiempo = 1
   WHERE estadoPreparacion = 'Pendiente'
     AND fechaInicio IS NOT NULL
     AND alertaTiempo = 0
     AND TIMESTAMPDIFF(SECOND, fechaInicio, NOW()) > 1200;
END$$

-- Despacho.notificarDomiciliario(): asigna el pedido listo a un domiciliario.
CREATE PROCEDURE sp_asignar_domiciliario(IN p_idPedido INT UNSIGNED, IN p_idDomiciliario INT UNSIGNED)
BEGIN
  IF NOT EXISTS (SELECT 1 FROM comanda_kds WHERE idPedido = p_idPedido AND estadoPreparacion = 'Listo') THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'CU-04: el pedido todavia no esta Listo en cocina';
  END IF;

  INSERT INTO despacho (idPedido, idDomiciliario, fechaAsignacion, fechaNotificacion)
  VALUES (p_idPedido, p_idDomiciliario, NOW(), NOW());
END$$

-- CU-05: el domiciliario retira el pedido (pasa a En Ruta).
CREATE PROCEDURE sp_retirar_pedido(IN p_idPedido INT UNSIGNED, IN p_idUsuario INT UNSIGNED)
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  IF NOT EXISTS (SELECT 1 FROM despacho WHERE idPedido = p_idPedido) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'El pedido no tiene domiciliario asignado';
  END IF;

  START TRANSACTION;
    SET @idUsuarioActual = p_idUsuario;
    UPDATE pedido SET estado = 'En Ruta' WHERE idPedido = p_idPedido;
    UPDATE despacho SET fechaSalida = NOW() WHERE idPedido = p_idPedido;
  COMMIT;
END$$

-- CU-05: entrega al cliente (pasa a Entregado).
CREATE PROCEDURE sp_marcar_entregado(IN p_idPedido INT UNSIGNED, IN p_idUsuario INT UNSIGNED)
BEGIN
  DECLARE EXIT HANDLER FOR SQLEXCEPTION
  BEGIN
    ROLLBACK;
    RESIGNAL;
  END;

  START TRANSACTION;
    SET @idUsuarioActual = p_idUsuario;
    UPDATE pedido SET estado = 'Entregado' WHERE idPedido = p_idPedido;
    UPDATE despacho SET fechaEntrega = NOW() WHERE idPedido = p_idPedido;
  COMMIT;
END$$

DELIMITER ;

-- Opcional: ejecutar las alertas rojas cada minuto (requiere event_scheduler=ON).
-- CREATE EVENT ev_alertas_kds
--   ON SCHEDULE EVERY 1 MINUTE
--   DO CALL sp_actualizar_alertas_tiempo();

-- =====================================================================
-- 4. VISTAS (lo que consume cada pantalla)
-- =====================================================================

-- Pantalla KDS (RF-02 / RF-04): comandas pendientes con semaforo verde/rojo.
CREATE VIEW v_comanda_kds AS
SELECT c.idComanda,
       p.idPedido,
       p.fechaHora,
       cl.nombre AS cliente,
       GROUP_CONCAT(CONCAT(d.cantidad, ' x ', d.producto) ORDER BY d.idDetalle SEPARATOR ', ') AS items,
       p.observaciones,
       c.estadoPreparacion,
       TIMESTAMPDIFF(MINUTE, c.fechaInicio, COALESCE(c.fechaListo, NOW())) AS minutosTranscurridos,
       CASE
         WHEN c.estadoPreparacion = 'Listo' THEN 'Listo'
         WHEN TIMESTAMPDIFF(SECOND, c.fechaInicio, NOW()) > 1200 THEN 'Rojo'
         ELSE 'Verde'
       END AS semaforo
  FROM comanda_kds c
  JOIN pedido p          ON p.idPedido = c.idPedido
  JOIN cliente cl        ON cl.idCliente = p.idCliente
  JOIN detalle_pedido d  ON d.idPedido = p.idPedido
 WHERE c.estadoPreparacion = 'Pendiente'
 GROUP BY c.idComanda, p.idPedido, p.fechaHora, cl.nombre, p.observaciones,
          c.estadoPreparacion, c.fechaInicio, c.fechaListo
 ORDER BY c.fechaInicio;

-- Vista del domiciliario: datos precisos de direccion y telefono.
CREATE VIEW v_despacho_domiciliario AS
SELECT ds.idDomiciliario,
       p.idPedido,
       p.estado,
       cl.nombre    AS cliente,
       cl.telefono,
       p.direccionEntrega,
       p.observaciones,
       ds.fechaAsignacion,
       ds.fechaSalida,
       ds.fechaEntrega
  FROM despacho ds
  JOIN pedido p   ON p.idPedido = ds.idPedido
  JOIN cliente cl ON cl.idCliente = p.idCliente
 WHERE p.estado IN ('En Cocina', 'En Ruta');

-- Seguimiento general de pedidos (RF-05).
CREATE VIEW v_seguimiento_pedido AS
SELECT p.idPedido,
       p.fechaHora,
       p.canal,
       cl.nombre  AS cliente,
       cl.telefono,
       p.estado,
       p.total,
       COALESCE(pg.validado, 0) AS pagoValidado,
       TIMESTAMPDIFF(MINUTE, p.fechaHora, COALESCE(ds.fechaEntrega, NOW())) AS minutosDesdeRegistro
  FROM pedido p
  JOIN cliente cl    ON cl.idCliente = p.idCliente
  LEFT JOIN pago pg  ON pg.idPedido = p.idPedido
  LEFT JOIN despacho ds ON ds.idPedido = p.idPedido;

-- Control de caja del dueno (NEC-03): pedidos sin pago validado.
CREATE VIEW v_pedidos_sin_pago_validado AS
SELECT p.idPedido, p.fechaHora, cl.nombre AS cliente, p.total,
       p.estado, pg.medioPago, (pg.urlComprobante IS NOT NULL) AS tieneComprobante
  FROM pedido p
  JOIN cliente cl   ON cl.idCliente = p.idCliente
  LEFT JOIN pago pg ON pg.idPedido = p.idPedido
 WHERE pg.idPago IS NULL OR pg.validado = 0;

-- Ventas diarias para el administrador.
CREATE VIEW v_ventas_diarias AS
SELECT DATE(p.fechaHora) AS dia,
       COUNT(*)          AS pedidos,
       SUM(p.total)      AS totalVendido,
       SUM(p.canal = 'WhatsApp')  AS porWhatsApp,
       SUM(p.canal = 'Instagram') AS porInstagram
  FROM pedido p
  JOIN pago pg ON pg.idPedido = p.idPedido AND pg.validado = 1
 GROUP BY DATE(p.fechaHora);

-- =====================================================================
-- 5. DATOS DE EJEMPLO (para probar el flujo completo)
-- =====================================================================

INSERT INTO rol (nombre, descripcion) VALUES
  ('Administrador',    'Dueno: control de caja y consulta de ventas'),
  ('Cajera',           'Encargada de caja: atiende chats, toma datos y gestiona pagos'),
  ('Auxiliar de Cocina','Prepara pedidos desde la pantalla KDS'),
  ('Domiciliario',     'Transporta el pedido y marca la entrega');

INSERT INTO usuario (idRol, nombre, telefono, username, passwordHash) VALUES
  (1, 'Administrador Demo', '3000000001', 'admin',   'CAMBIAR_POR_HASH'),
  (2, 'Cajera Demo',        '3000000002', 'cajera',  'CAMBIAR_POR_HASH'),
  (3, 'Auxiliar Demo',      '3000000003', 'cocina',  'CAMBIAR_POR_HASH'),
  (4, 'Domiciliario Demo',  '3000000004', 'domi',    'CAMBIAR_POR_HASH');

INSERT INTO cliente (nombre, telefono, direccion) VALUES
  ('Cliente Uno',  '3101111111', 'Calle 10 # 5-20'),
  ('Cliente Dos',  '3102222222', 'Carrera 7 # 12-45'),
  ('Cliente Tres', '3103333333', 'Calle 3 # 8-15');

-- Pedido 1: recorre todo el flujo hasta Entregado.
INSERT INTO pedido (idCliente, idUsuarioCajera, canal, direccionEntrega, observaciones)
VALUES (1, 2, 'WhatsApp', 'Calle 10 # 5-20', 'Sin cebolla');
INSERT INTO detalle_pedido (idPedido, producto, cantidad, subtotal) VALUES
  (1, 'Hamburguesa sencilla', 2, 36000),
  (1, 'Perro caliente',       1, 12000);
INSERT INTO pago (idPedido, medioPago, urlComprobante)
VALUES (1, 'Transferencia', 'https://ejemplo.local/comprobantes/pedido1.jpg');

CALL sp_validar_pago(1, 2);
CALL sp_enviar_a_cocina(1, 2);
CALL sp_marcar_listo(1);
CALL sp_asignar_domiciliario(1, 4);
CALL sp_retirar_pedido(1, 4);
CALL sp_marcar_entregado(1, 4);

-- Pedido 2: ya esta en cocina (pendiente).
INSERT INTO pedido (idCliente, idUsuarioCajera, canal, direccionEntrega)
VALUES (2, 2, 'Instagram', 'Carrera 7 # 12-45');
INSERT INTO detalle_pedido (idPedido, producto, cantidad, subtotal) VALUES
  (2, 'Picada para 2', 1, 38000);
INSERT INTO pago (idPedido, medioPago, urlComprobante)
VALUES (2, 'Transferencia', 'https://ejemplo.local/comprobantes/pedido2.jpg');
CALL sp_validar_pago(2, 2);
CALL sp_enviar_a_cocina(2, 2);

-- Pedido 3: registrado, todavia sin comprobante (no puede pasar a cocina).
INSERT INTO pedido (idCliente, idUsuarioCajera, canal, direccionEntrega)
VALUES (3, 2, 'WhatsApp', 'Calle 3 # 8-15');
INSERT INTO detalle_pedido (idPedido, producto, cantidad, subtotal) VALUES
  (3, 'Hamburguesa doble', 1, 24000);
INSERT INTO pago (idPedido, medioPago) VALUES (3, 'Transferencia');

-- =====================================================================
-- 6. CONSULTAS DE PRUEBA (descomentar para probar)
-- =====================================================================
-- SELECT * FROM v_comanda_kds;                  -- pantalla de cocina
-- SELECT * FROM v_seguimiento_pedido;           -- estados de todos los pedidos
-- SELECT * FROM historial_estado_pedido WHERE idPedido = 1 ORDER BY idHistorial;
-- SELECT * FROM v_pedidos_sin_pago_validado;    -- control de caja
-- SELECT * FROM v_ventas_diarias;
-- CALL sp_enviar_a_cocina(3, 2);                -- debe fallar: RF-03 (sin comprobante validado)
