"""Páginas protegidas de los reportes operativos de Bodega."""
import re
from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .decorators import permiso_requerido
from .models import Categoria, Proveedor, Solicitud, Sucursal
from .reportes import (
    FILTROS_REQUERIDOS, NIVELES, PERMISOS_REPORTE, PREGUNTAS,
    REPORTES, construye_reporte, metricas_inventario, ultimo_mes_calendario,
)


REFERENCIAS = {
    'categoria': Categoria, 'proveedor': Proveedor,
    'sucursal': Sucursal, 'solicitud': Solicitud,
}
ETIQUETAS = {'categoria': 'Categoría', 'proveedor': 'Proveedor',
             'sucursal': 'Sucursal', 'solicitud': 'Solicitud',
             'desde': 'Fecha inicial', 'hasta': 'Fecha final'}

TITULOS_GRUPOS = {
    'Básico': 'Inventario',
    'Intermedio': 'Proveedores y solicitudes',
    'Avanzado': 'Control de existencias',
    'Análisis': 'Análisis de inventario',
}

NOTAS_OPERATIVAS = {
    3: 'Incluye productos con existencias menores al stock mínimo.',
    6: 'Incluye los productos asociados al proveedor seleccionado.',
    9: 'Se muestran todos los estados, incluso los que no tienen solicitudes.',
    10: 'El período incluye las fechas inicial y final.',
    11: 'Las cantidades corresponden a unidades solicitadas, en todos los estados.',
    12: 'Las cantidades corresponden a unidades solicitadas, en todos los estados.',
    13: 'En caso de empate se muestra el primer proveedor por nombre.',
    15: 'Productos que no figuran en ninguna solicitud de sucursales.',
    19: 'Promedio de unidades totales solicitadas por solicitud.',
    20: 'El período incluye las fechas inicial y final y las solicitudes de todos los estados.',
}


def _validar_filtros(request, numero):
    datos = {campo: request.GET.get(campo, '').strip() for campo in (*REFERENCIAS, 'desde', 'hasta')}
    for campo in REFERENCIAS:
        datos[f'{campo}_manual'] = request.GET.get(f'{campo}_manual', '').strip()
        if datos[f'{campo}_manual']:
            datos[campo] = datos[f'{campo}_manual']
    filtros, errores = {}, {}
    for campo, modelo in REFERENCIAS.items():
        valor = datos[campo]
        if not valor:
            continue
        if not request.user.has_perm(f'bodega.view_{modelo._meta.model_name}'):
            raise PermissionDenied('No tienes permiso para consultar ese filtro.')
        if not re.fullmatch(r'[1-9][0-9]{0,17}', valor):
            errores[campo] = 'Ingresa un identificador entero positivo válido.'
        else:
            consulta = modelo.objects
            objeto = consulta.filter(pk=int(valor)).first()
            if objeto is None:
                errores[campo] = 'El registro seleccionado no existe.'
            else:
                filtros[campo] = int(valor)
                filtros[f'{campo}_texto'] = (
                    f'Solicitud #{objeto.pk} · {timezone.localtime(objeto.fecha):%d-%m-%Y}'
                    if campo == 'solicitud' else objeto.nombre
                )
    for campo in ('desde', 'hasta'):
        valor = datos[campo]
        if valor:
            try:
                if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', valor):
                    raise ValueError
                filtros[campo] = date.fromisoformat(valor)
                if not date(1000, 1, 1) <= filtros[campo] <= date(9999, 12, 30):
                    raise ValueError
            except ValueError:
                errores[campo] = 'Ingresa una fecha válida entre 1000-01-01 y 9999-12-30 con formato AAAA-MM-DD.'
    for campo in FILTROS_REQUERIDOS.get(numero, ()):
        if not datos[campo]:
            errores[campo] = 'Este filtro es obligatorio para el reporte seleccionado.'
    if filtros.get('desde') and filtros.get('hasta') and filtros['desde'] > filtros['hasta']:
        errores['hasta'] = 'La fecha final debe ser igual o posterior a la inicial.'
    return datos, filtros, errores


def _sugerencias(usuario):
    """Las ayudas no cargan tablas completas ni revelan entidades sin permiso."""
    salida = {}
    for campo, modelo in REFERENCIAS.items():
        if usuario.has_perm(f'bodega.view_{modelo._meta.model_name}'):
            consulta = modelo.objects.order_by('-pk') if campo == 'solicitud' else modelo.objects.order_by('nombre', 'pk')
            salida[{'categoria': 'categorias', 'proveedor': 'proveedores',
                    'sucursal': 'sucursales', 'solicitud': 'solicitudes'}[campo]] = consulta[:100]
        else:
            salida[{'categoria': 'categorias', 'proveedor': 'proveedores',
                    'sucursal': 'sucursales', 'solicitud': 'solicitudes'}[campo]] = []
    return salida


def _autorizado(usuario, numero):
    return usuario.has_perms([f'bodega.view_{modelo}' for modelo in PERMISOS_REPORTE[numero]])


def _campos_reporte(numero, datos, sugerencias):
    nombres = {'categoria': 'categorias', 'proveedor': 'proveedores',
               'sucursal': 'sucursales', 'solicitud': 'solicitudes'}
    campos = []
    for nombre in FILTROS_REQUERIDOS.get(numero, ()):
        campo = {'nombre': nombre, 'etiqueta': ETIQUETAS[nombre],
                 'valor': datos.get(nombre, ''),
                 'fecha': nombre in ('desde', 'hasta'),
                 'id_html': f'reporte-{numero}-{nombre}'}
        if not campo['fecha']:
            campo['manual'] = datos.get(f'{nombre}_manual', '')
            campo['opciones'] = [
                {'id': objeto.pk,
                 'etiqueta': (f'Solicitud #{objeto.pk} · {timezone.localtime(objeto.fecha):%d-%m-%Y}'
                              if nombre == 'solicitud' else objeto.nombre)}
                for objeto in sugerencias[nombres[nombre]]
            ]
            # Un ID que ya fue elegido sigue visible si quedó fuera de las
            # primeras cien opciones. La vista valida su existencia aparte.
            if campo['valor'] and not any(str(opcion['id']) == str(campo['valor']) for opcion in campo['opciones']):
                campo['manual'] = campo['manual'] or campo['valor']
        campos.append(campo)
    return campos


@login_required
@permiso_requerido('bodega.view_producto')
@require_GET
def panel_consultas(request):
    metricas = metricas_inventario()
    if request.user.has_perm('bodega.view_solicitud'):
        metricas['solicitudes_pendientes'] = Solicitud.objects.filter(estado='PENDIENTE').count()
    sugerencias = _sugerencias(request.user)
    grupos = []
    for nivel, numeros in NIVELES:
        tarjetas = []
        for numero in numeros:
            autorizado = _autorizado(request.user, numero)
            tarjetas.append({
                'numero': numero, 'titulo': REPORTES[numero],
                'pregunta': PREGUNTAS[numero],
                'autorizada': autorizado,
                'campos': _campos_reporte(numero, {}, sugerencias) if autorizado else [],
            })
        grupos.append({'nivel': nivel, 'titulo': TITULOS_GRUPOS[nivel], 'tarjetas': tarjetas})
    return render(request, 'bodega/panel_consultas.html', {
        'metricas': metricas, 'grupos': grupos,
        'puede_ver_solicitudes': request.user.has_perm('bodega.view_solicitud'),
    })


@login_required
@permiso_requerido('bodega.view_producto')
@require_GET
def reportes(request):
    valor_numero = request.GET.get('n', '1')
    errores = {}
    numero = int(valor_numero) if re.fullmatch(r'[0-9]{1,2}', valor_numero) else None
    if numero in (4, 14, 18):
        raise Http404('El reporte solicitado no está disponible.')
    if numero not in REPORTES:
        numero = None
        errores['n'] = 'Selecciona uno de los reportes disponibles.'
    if numero is not None:
        permisos = [f'bodega.view_{modelo}' for modelo in PERMISOS_REPORTE[numero]]
        if not request.user.has_perms(permisos):
            raise PermissionDenied('Tu cuenta no tiene permiso para las entidades de este reporte.')
    datos, filtros, errores_filtros = _validar_filtros(request, numero)
    errores.update(errores_filtros)
    contexto = {
        'opciones_reportes': list(REPORTES.items()), 'numero': numero,
        'datos': datos, 'errores': [(ETIQUETAS.get(campo, 'Reporte'), mensaje) for campo, mensaje in errores.items()],
        'requeridos': ', '.join(ETIQUETAS[campo] for campo in FILTROS_REQUERIDOS.get(numero, ())),
        'reporte': None,
        'nota_operativa': NOTAS_OPERATIVAS.get(numero, ''),
    }
    sugerencias = _sugerencias(request.user)
    contexto.update(sugerencias)
    contexto['campos'] = _campos_reporte(numero, datos, sugerencias)
    contexto['pregunta'] = PREGUNTAS.get(numero, 'Elige un reporte desde el panel de consultas.')
    if not errores:
        with timezone.override('America/Santiago'):
            reporte = construye_reporte(numero, filtros)
            pagina = Paginator(reporte['filas'], 25).get_page(request.GET.get('page'))
            resultados = list(pagina.object_list)
        contexto.update({
            'reporte': reporte, 'pagina': pagina,
            'criterios': [(ETIQUETAS[campo], filtros.get(f'{campo}_texto', datos[campo]))
                          for campo in FILTROS_REQUERIDOS.get(numero, ())],
            'encabezados': [etiqueta for _, etiqueta in reporte['columnas']],
            'filas': [[fila.get(campo) for campo, _ in reporte['columnas']] for fila in resultados],
        })
        if numero == 16:
            desde, hasta = ultimo_mes_calendario()
            contexto['nota_operativa'] = f'Salidas registradas entre el {desde:%d/%m/%Y} y el {hasta:%d/%m/%Y}.'
        if numero == 19:
            clave, etiqueta = reporte['columnas'][0]
            contexto['metrica_resultado'] = {
                'etiqueta': etiqueta, 'valor': resultados[0][clave],
                'moneda': False,
            }
    return render(request, 'bodega/reportes.html', contexto)
