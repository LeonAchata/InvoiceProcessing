"""
Módulo de gestión de base de datos PostgreSQL.
Manejo de conexiones async y operaciones CRUD para facturas.
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncpg

logger = logging.getLogger("DatabaseManager")


class DatabaseManager:
    """
    Gestor de base de datos PostgreSQL con pool de conexiones async.
    Patrón similar a Pipeline para mantener consistencia en el proyecto.
    """
    
    def __init__(self, database_url: str):
        """
        Inicializa el gestor con la URL de conexión.
        
        Args:
            database_url: String de conexión PostgreSQL
        """
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None
        logger.info("DatabaseManager inicializado")
    
    async def conectar(self) -> None:
        """Establece el pool de conexiones a PostgreSQL."""
        try:
            self.pool = await asyncpg.create_pool(
                dsn=self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60,
                timeout=30
            )
            logger.info("Pool de conexiones establecido correctamente")
            
            # Verificar conexión
            async with self.pool.acquire() as conn:
                version = await conn.fetchval('SELECT version()')
                logger.info(f"Conectado a: {version}")
                
        except Exception as e:
            logger.error(f"Error conectando a PostgreSQL: {e}")
            raise
    
    async def cerrar_conexion(self) -> None:
        """Cierra el pool de conexiones."""
        if self.pool:
            await self.pool.close()
            logger.info("Pool de conexiones cerrado")
    
    async def verificar_conexion(self) -> bool:
        """
        Verifica que la conexión esté activa.
        
        Returns:
            True si la conexión es exitosa, False en caso contrario
        """
        if not self.pool:
            return False
        
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval('SELECT 1')
            return True
        except Exception as e:
            logger.error(f"Error verificando conexión: {e}")
            return False
    
    async def guardar_factura(
        self, 
        datos: Dict[str, Any],
        filename: Optional[str] = None
    ) -> int:
        """
        Guarda una factura completa en PostgreSQL (facturas + items).
        Ejecuta todo en una transacción para garantizar atomicidad.
        
        Args:
            datos: Diccionario con datos de la factura (formato del frontend)
            filename: Nombre del archivo PDF original (opcional)
        
        Returns:
            ID de la factura insertada
        
        Raises:
            Exception: Si hay error en la transacción
        """
        if not self.pool:
            raise Exception("Pool de conexiones no inicializado. Llama a conectar() primero.")
        
        # Generar código de factura único
        codigo_factura = f"FACT-{uuid.uuid4().hex[:8].upper()}"
        
        # Extraer detracción si existe
        detraccion = datos.get('detraccion')
        detraccion_porcentaje = detraccion.get('porcentaje') if detraccion else None
        detraccion_monto = detraccion.get('monto') if detraccion else None
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    # 1. Insertar factura principal
                    factura_id = await conn.fetchval(
                        """
                        INSERT INTO facturas (
                            codigo_factura,
                            fecha_emision,
                            codigo_cliente,
                            razon_social_cliente,
                            direccion_cliente,
                            distrito,
                            forma_pago,
                            moneda,
                            subtotal,
                            igv,
                            total,
                            detraccion_porcentaje,
                            detraccion_monto,
                            archivo_pdf_path,
                            estado,
                            datos_raw
                        ) VALUES (
                            $1, CURRENT_DATE, $2, $3, $4, $5, $6, $7, $8, $9, $10, 
                            $11, $12, $13, 'procesada', $14
                        ) RETURNING id
                        """,
                        codigo_factura,
                        datos.get('codigo_cliente'),
                        datos.get('razon_social_cliente'),
                        datos.get('direccion_cliente'),
                        datos.get('distrito'),
                        datos.get('forma_pago'),
                        datos.get('moneda'),
                        datos.get('subtotal'),
                        datos.get('igv'),
                        datos.get('total'),
                        detraccion_porcentaje,
                        detraccion_monto,
                        filename,  # Guardar nombre del archivo
                        datos  # JSONB completo para auditoría
                    )
                    
                    logger.info(f"Factura insertada con ID: {factura_id}, código: {codigo_factura}")
                    
                    # 2. Insertar items de la factura
                    items = datos.get('items', [])
                    if items:
                        items_insertados = await self._insertar_items(conn, factura_id, items)
                        logger.info(f"{items_insertados} items insertados para factura {factura_id}")
                    else:
                        logger.warning(f"Factura {factura_id} guardada sin items")
                    
                    return factura_id
                    
                except Exception as e:
                    logger.error(f"Error en transacción de guardado: {e}")
                    raise Exception(f"Error guardando factura: {str(e)}")
    
    async def _insertar_items(
        self, 
        conn: asyncpg.Connection, 
        factura_id: int, 
        items: List[Dict[str, Any]]
    ) -> int:
        """
        Inserta múltiples items de factura en una sola operación.
        Método interno llamado dentro de la transacción.
        
        Args:
            conn: Conexión activa de asyncpg
            factura_id: ID de la factura padre
            items: Lista de items a insertar
        
        Returns:
            Cantidad de items insertados
        """
        if not items:
            return 0
        
        # Preparar datos para inserción batch
        items_data = [
            (
                factura_id,
                item.get('descripcion'),
                item.get('cantidad'),
                item.get('precio_unitario'),
                item.get('subtotal')
            )
            for item in items
            if item.get('descripcion')  # Solo items con descripción
        ]
        
        if not items_data:
            logger.warning("No hay items válidos para insertar")
            return 0
        
        # Inserción batch (más eficiente que loops)
        result = await conn.executemany(
            """
            INSERT INTO factura_items (
                factura_id, 
                descripcion, 
                cantidad, 
                precio_unitario, 
                subtotal
            ) VALUES ($1, $2, $3, $4, $5)
            """,
            items_data
        )
        
        return len(items_data)
    
    async def obtener_factura(self, factura_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene una factura completa con sus items.
        
        Args:
            factura_id: ID de la factura
        
        Returns:
            Diccionario con factura e items, o None si no existe
        """
        if not self.pool:
            raise Exception("Pool de conexiones no inicializado")
        
        async with self.pool.acquire() as conn:
            # Obtener factura
            factura = await conn.fetchrow(
                "SELECT * FROM facturas WHERE id = $1",
                factura_id
            )
            
            if not factura:
                return None
            
            # Obtener items
            items = await conn.fetch(
                "SELECT * FROM factura_items WHERE factura_id = $1",
                factura_id
            )
            
            # Convertir a dict
            factura_dict = dict(factura)
            factura_dict['items'] = [dict(item) for item in items]
            
            return factura_dict
    
    async def listar_facturas(
        self, 
        limite: int = 50, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Lista facturas con paginación.
        
        Args:
            limite: Cantidad máxima de registros
            offset: Número de registros a saltar
        
        Returns:
            Lista de facturas (sin items)
        """
        if not self.pool:
            raise Exception("Pool de conexiones no inicializado")
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM facturas 
                ORDER BY fecha_registro DESC 
                LIMIT $1 OFFSET $2
                """,
                limite,
                offset
            )
            
            return [dict(row) for row in rows]
    
    async def obtener_estadisticas(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas generales de facturas.
        
        Returns:
            Diccionario con métricas
        """
        if not self.pool:
            raise Exception("Pool de conexiones no inicializado")
        
        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_facturas,
                    SUM(total) as monto_total,
                    AVG(total) as promedio_factura,
                    COUNT(DISTINCT codigo_cliente) as total_clientes
                FROM facturas
                """
            )
            
            return dict(stats) if stats else {}