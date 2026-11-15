-- =====================================================================
--  Ajustes sobre pedidocentral.sql para conectar la interfaz web
--  Ejecutar DESPUÉS de pedidocentral.sql:
--     mysql -u root -p pedidocentral < database/ajustes.sql
-- =====================================================================
USE pedidocentral;

-- 1. La interfaz maneja 5 canales (antes solo WhatsApp e Instagram).
ALTER TABLE pedido
  MODIFY canal ENUM('WhatsApp','App de domicilio','Instagram','Facebook','Llamada') NOT NULL;

-- 2. Se agrega el estado Cancelado (pedido y trazabilidad).
ALTER TABLE pedido
  MODIFY estado ENUM('Registrado','En Cocina','En Ruta','Entregado','Cancelado')
  NOT NULL DEFAULT 'Registrado';

ALTER TABLE historial_estado_pedido
  MODIFY estadoAnterior ENUM('Registrado','En Cocina','En Ruta','Entregado','Cancelado') NULL,
  MODIFY estadoNuevo    ENUM('Registrado','En Cocina','En Ruta','Entregado','Cancelado') NOT NULL;

-- 3. El trigger de transiciones ahora permite cancelar antes de salir En Ruta.
DROP TRIGGER IF EXISTS trg_pedido_bu;
DELIMITER $$
CREATE TRIGGER trg_pedido_bu
BEFORE UPDATE ON pedido
FOR EACH ROW
BEGIN
  IF NEW.estado <> OLD.estado THEN
    IF NOT (   (OLD.estado = 'Registrado' AND NEW.estado = 'En Cocina')
            OR (OLD.estado = 'En Cocina'  AND NEW.estado = 'En Ruta')
            OR (OLD.estado = 'En Ruta'    AND NEW.estado = 'Entregado')
            OR (OLD.estado IN ('Registrado','En Cocina') AND NEW.estado = 'Cancelado')) THEN
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
DELIMITER ;

-- 4. Las vistas de caja no cuentan pedidos cancelados.
CREATE OR REPLACE VIEW v_ventas_diarias AS
SELECT DATE(p.fechaHora) AS dia,
       COUNT(*)          AS pedidos,
       SUM(p.total)      AS totalVendido,
       SUM(p.canal = 'WhatsApp')  AS porWhatsApp,
       SUM(p.canal = 'Instagram') AS porInstagram
  FROM pedido p
  JOIN pago pg ON pg.idPedido = p.idPedido AND pg.validado = 1
 WHERE p.estado <> 'Cancelado'
 GROUP BY DATE(p.fechaHora);

CREATE OR REPLACE VIEW v_pedidos_sin_pago_validado AS
SELECT p.idPedido, p.fechaHora, cl.nombre AS cliente, p.total,
       p.estado, pg.medioPago, (pg.urlComprobante IS NOT NULL) AS tieneComprobante
  FROM pedido p
  JOIN cliente cl   ON cl.idCliente = p.idCliente
  LEFT JOIN pago pg ON pg.idPedido = p.idPedido
 WHERE (pg.idPago IS NULL OR pg.validado = 0) AND p.estado <> 'Cancelado';
