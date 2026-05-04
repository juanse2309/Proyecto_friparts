/**
 * nomina.js - Sistema de Consolidado y Cierre de Nómina
 * Permite al equipo de RRHH visualizar horas acumuladas y ejecutar cortes contables.
 */

const ModuloNomina = (function () {
    let datosConsolidados = {};
    let detalleDiario = [];
    let totalRegsPendientes = 0;

    async function inicializar() {
        console.log("💼 ModuloNomina: Inicializando...");
        await cargarConsolidado();
    }

    async function cargarConsolidado() {
        const body = document.getElementById('nomina-body');
        const alertPeriodo = document.getElementById('nomina-alerta-periodo');
        const btnCorte = document.getElementById('btn-ejecutar-corte');

        body.innerHTML = '<tr><td colspan="4" class="text-center py-5"><i class="fas fa-spinner fa-spin text-primary me-2"></i> Consolidando información...</td></tr>';

        try {
            const response = await fetch('/api/asistencia/consolidado_pendiente');
            const data = await response.json();

            if (data.status === 'success') {
                datosConsolidados = data.consolidado; // Ahora es un Array
                detalleDiario = data.detalle_diario || [];
                totalRegsPendientes = data.total_registros_pendientes;

                // Actualizar alerta de periodo
                if (alertPeriodo) {
                    alertPeriodo.style.setProperty('display', 'flex', 'important');
                    document.getElementById('nomina-txt-ultimo-corte').textContent =
                        `Último corte registrado: ${data.ultima_fecha_corte}. Procesando registros desde entonces.`;
                }

                renderizarTabla();

                // Habilitar/Deshabilitar botón de corte
                btnCorte.disabled = totalRegsPendientes === 0;
            } else {
                throw new Error(data.message);
            }
        } catch (error) {
            console.error("Error cargando consolidado:", error);
            body.innerHTML = '<tr><td colspan="4" class="text-center py-5 text-danger">Error al obtener datos pendientes</td></tr>';
        }
    }

    function renderizarTabla() {
        const body = document.getElementById('nomina-body');

        if (!datosConsolidados || datosConsolidados.length === 0) {
            body.innerHTML = '<tr><td colspan="4" class="text-center py-5 text-muted">No hay registros de asistencia en el periodo actual</td></tr>';
            return;
        }

        body.innerHTML = datosConsolidados.map(d => {
            return `
                <tr>
                    <td class="ps-4 fw-bold">${d.colaborador}</td>
                    <td class="text-center">${d.horas_ordinarias}</td>
                    <td class="text-center">${d.horas_extras}</td>
                    <td class="text-center"><span class="badge bg-soft-info text-info border">${d.estado || 'Pendiente'}</span></td>
                </tr>
            `;
        }).join('');
    }

    async function ejecutarCorte() {
        if (totalRegsPendientes === 0) return;

        const { isConfirmed } = await Swal.fire({
            title: '¿Ejecutar Corte de Nómina?',
            text: `Se procesarán ${totalRegsPendientes} registros y se generará el archivo CSV detallado. Esta acción sellará el periodo actual.`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#22c55e',
            cancelButtonColor: '#ef4444',
            confirmButtonText: 'Sí, ejecutar y descargar',
            cancelButtonText: 'Cancelar'
        });

        if (!isConfirmed) return;

        // 1. Generar y Descargar CSV detallado
        generarCSV();

        // 2. Notificar al backend para sellar el periodo
        try {
            const user = (typeof AuthModule !== 'undefined' && AuthModule.currentUser) ? AuthModule.currentUser.nombre : 'Sistema';
            const response = await fetch('/api/asistencia/ejecutar_corte', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    total_registros: totalRegsPendientes,
                    usuario: user
                })
            });

            const res = await response.json();
            if (res.status === 'success') {
                Swal.fire('Corte Exitoso', res.message, 'success');
                await cargarConsolidado(); // Recargar (debería quedar vacío)
            } else {
                throw new Error(res.message);
            }
        } catch (error) {
            console.error("Error al sellar corte:", error);
            Swal.fire('Error', 'No se pudo registrar el cierre en la base de datos, pero el CSV fue generado.', 'warning');
        }
    }

    function generarCSV() {
        // Nombrado dinámico: Nomina_Friparts_Mes_Dia_Año.csv
        const fecha = new Date();
        const meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
        const nombreArchivo = `Nomina_Friparts_${meses[fecha.getMonth()]}_${fecha.getDate()}_${fecha.getFullYear()}.csv`;

        // Agrupar detalle diario por colaborador
        const porColaborador = {};
        detalleDiario.forEach(reg => {
            if (!porColaborador[reg.colaborador]) {
                porColaborador[reg.colaborador] = [];
            }
            porColaborador[reg.colaborador].push(reg);
        });

        // Construir CSV con desglose diario + totales
        let csvContent = "Colaborador;Fecha;Ingreso;Salida;Horas Ordinarias;Horas Extras;Motivo;Comentarios\n";

        const colaboradores = Object.keys(porColaborador).sort();
        colaboradores.forEach(nombre => {
            const dias = porColaborador[nombre];
            let totalOrd = 0;
            let totalExt = 0;

            // Líneas diarias
            dias.forEach(d => {
                const motivo = (d.motivo || '').toString().replace(/;/g, ' ');
                const comentarios = (d.comentarios || '').toString().replace(/;/g, ' ');
                csvContent += `${nombre};${d.fecha};${d.ingreso};${d.salida};${d.horas_ordinarias};${d.horas_extras};${motivo};${comentarios}\n`;
                totalOrd += d.horas_ordinarias;
                totalExt += d.horas_extras;
            });

            // Línea de subtotal por persona
            csvContent += `TOTAL ${nombre};;;;${totalOrd};${totalExt};;\n`;
            // Línea en blanco para separar
            csvContent += `;;;;;;;\n`;
        });

        // Crear Blob y descargar
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement("a");
        if (link.download !== undefined) {
            const url = URL.createObjectURL(blob);
            link.setAttribute("href", url);
            link.setAttribute("download", nombreArchivo);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    }

    return {
        inicializar,
        cargarConsolidado,
        ejecutarCorte
    };
})();
