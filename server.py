"""
Servidor MCP para integração com a API do SmartOLT.

Autenticação: a API do SmartOLT usa um header "X-Token" com sua API key,
e a URL base é https://<seu-subdominio>.smartolt.com/api/...

Configure as variáveis de ambiente antes de rodar:
  SMARTOLT_SUBDOMAIN  -> ex: "minhaisp" (de https://minhaisp.smartolt.com)
  SMARTOLT_API_KEY    -> gerada em Settings > API KEY no painel do SmartOLT

Como rodar localmente (teste):
  export SMARTOLT_SUBDOMAIN="minhaisp"
  export SMARTOLT_API_KEY="sua-chave"
  python server.py

Isso sobe um servidor MCP via Streamable HTTP em http://0.0.0.0:8000/mcp
Para o Claude.ai conseguir se conectar, esse endereço precisa estar
publicamente acessível na internet (deploy em Railway, Fly.io, Render,
Vercel, um VPS com HTTPS, etc.) — não funciona atrás de VPN/firewall
sem liberar os IPs da Anthropic.
"""

import os
import httpx
from mcp.server import MCPServer

SUBDOMAIN = os.environ.get("SMARTOLT_SUBDOMAIN", "")
API_KEY = os.environ.get("SMARTOLT_API_KEY", "")
BASE_URL = f"https://{SUBDOMAIN}.smartolt.com/api"

mcp = MCPServer("smartolt")


async def _get(path: str, params: dict | None = None) -> dict:
    """Faz uma requisição GET autenticada à API do SmartOLT."""
    if not SUBDOMAIN or not API_KEY:
        return {"error": "SMARTOLT_SUBDOMAIN ou SMARTOLT_API_KEY não configurados no servidor."}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/{path}",
            headers={"X-Token": API_KEY},
            params=params or {},
        )
        resp.raise_for_status()
        return resp.json()


async def _post(path: str, data: dict | None = None) -> dict:
    """Faz uma requisição POST (form-data) autenticada à API do SmartOLT."""
    if not SUBDOMAIN or not API_KEY:
        return {"error": "SMARTOLT_SUBDOMAIN ou SMARTOLT_API_KEY não configurados no servidor."}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE_URL}/{path}",
            headers={"X-Token": API_KEY},
            data={k: v for k, v in (data or {}).items() if v is not None},
        )
        resp.raise_for_status()
        return resp.json()


async def _delete(path: str) -> dict:
    """Faz uma requisição DELETE autenticada à API do SmartOLT."""
    if not SUBDOMAIN or not API_KEY:
        return {"error": "SMARTOLT_SUBDOMAIN ou SMARTOLT_API_KEY não configurados no servidor."}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(f"{BASE_URL}/{path}", headers={"X-Token": API_KEY})
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
async def list_olts() -> dict:
    """Lista todas as OLTs cadastradas na conta SmartOLT (id, nome, IP, versão de hardware, portas telnet/snmp)."""
    return await _get("system/get_olts")


@mcp.tool()
async def get_olts_uptime_and_temperature() -> dict:
    """Retorna o uptime e a temperatura ambiente de cada OLT cadastrada."""
    return await _get("olt/get_olts_uptime_and_env_temperature")


@mcp.tool()
async def get_olt_cards(olt_id: str) -> dict:
    """Lista os cartões/placas (slots) instalados em uma OLT específica, com tipo, portas, versão e status.

    Args:
        olt_id: ID numérico da OLT (obtido via list_olts).
    """
    return await _get(f"system/get_olt_cards_details/{olt_id}")


@mcp.tool()
async def get_all_onus_details(
    page: str | None = None,
    page_size: str | None = None,
    updated_since: str | None = None,
    fields: str | None = None,
    olt_id: str | None = None,
    board: str | None = None,
    port: str | None = None,
    zone: str | None = None,
    odb: str | None = None,
    sn: str | None = None,
    external_id: str | None = None,
    name: str | None = None,
    address: str | None = None,
    onu_type_id: str | None = None,
    vlan: str | None = None,
    mode: str | None = None,
    wan_mode: str | None = None,
    administrative_status: str | None = None,
    tr069: str | None = None,
    catv: str | None = None,
    status: str | None = None,
    signal: str | None = None,
    authorized_after: str | None = None,
    authorized_before: str | None = None,
    status_changed_after: str | None = None,
) -> dict:
    """Retorna detalhes de todas as ONUs, com filtros opcionais.

    Use o filtro "status" para monitorar quedas de sinal (LOS) e falhas de
    energia (Power Fail) — ex: status="los,pwrfail" retorna só as ONUs nesses
    dois estados. Prefira sempre paginar (page/page_size) e usar "fields" para
    pedir só os campos que você precisa — sem filtros, a consulta pode ser
    pesada (equivalente a exportar o banco inteiro).

    Args:
        page: número da página (recomendado usar paginação).
        page_size: itens por página, 1–100 (padrão 100).
        updated_since: só ONUs cuja configuração mudou desde esta data
            (formato "AAAA-MM-DD HH:MM:SS"). Útil para sincronização
            incremental após um pull completo inicial.
        fields: lista de campos a retornar, separados por vírgula (ex:
            "sn,name,status"). Incluir service_ports/ethernet_ports/wifi_ports/
            voip_ports só quando necessário — pular acelera a resposta.
        olt_id: ID da OLT (opcional; vazio = todas as OLTs).
        board: placa/slot (opcional; vazio = todas as placas da OLT informada).
        port: porta PON (opcional; vazio = todas as portas da placa informada).
        zone: nome da zona cadastrada (alfanumérico, espaços, _ e -).
        odb: nome do ODB/splitter (alfanumérico, espaços, _ e -).
        sn: número de série da ONU.
        external_id: ID externo único da ONU.
        name: nome da ONU.
        address: endereço da ONU.
        onu_type_id: ID do tipo de ONU (aceita lista separada por vírgula).
        vlan: VLAN da ONU.
        mode: modo da ONU. Valores: "Routing", "Bridging".
        wan_mode: modo WAN da ONU. Valores: "Setup via ONU webpage", "DHCP",
            "Static", "PPPoE".
        administrative_status: status administrativo. Valores: "enabled", "disabled".
        tr069: status do TR069. Valores: "enabled", "disabled".
        catv: status do CATV. Valores: "enabled", "disabled".
        status: status da ONU. Valores: "online", "pwrfail", "los", "offline"
            — aceita lista separada por vírgula (ex: "los,pwrfail" para pegar
            só quedas de sinal e falta de energia).
        signal: nível de sinal. Valores: "very_good", "warning", "critical".
        authorized_after: ONUs autorizadas nesta data ou depois.
        authorized_before: ONUs autorizadas nesta data ou antes.
        status_changed_after: ONUs cujo status mudou nesta data ou depois.
    """
    params = {
        "page": page,
        "page_size": page_size,
        "updated_since": updated_since,
        "fields": fields,
        "olt_id": olt_id,
        "board": board,
        "port": port,
        "zone": zone,
        "odb": odb,
        "sn": sn,
        "external_id": external_id,
        "name": name,
        "address": address,
        "onu_type_id": onu_type_id,
        "vlan": vlan,
        "mode": mode,
        "wan_mode": wan_mode,
        "administrative_status": administrative_status,
        "tr069": tr069,
        "catv": catv,
        "status": status,
        "signal": signal,
        "authorized_after": authorized_after,
        "authorized_before": authorized_before,
        "status_changed_after": status_changed_after,
    }
    params = {k: v for k, v in params.items() if v is not None}
    return await _get("onu/get_all_onus_details", params=params)


@mcp.tool()
async def authorize_onu(
    olt_id: str,
    pon_type: str,
    sn: str,
    onu_type: str,
    onu_mode: str,
    zone: str,
    name: str,
    board: str | None = None,
    port: str | None = None,
    gpon_channel: str | None = None,
    epon_channel: str | None = None,
    custom_profile: str | None = None,
    cvlan: str | None = None,
    svlan: str | None = None,
    tag_transform_mode: str | None = None,
    use_other_all_tls_vlan: str | None = None,
    vlan: str | None = None,
    odb: str | None = None,
    address_or_comment: str | None = None,
    onu_external_id: str | None = None,
    upload_speed_profile_name: str | None = None,
    download_speed_profile_name: str | None = None,
) -> dict:
    """Autoriza uma ONU não configurada (unauthorized) em uma porta PON de uma OLT.

    Args:
        olt_id: ID da OLT na qual a ONU deve ser autorizada. (obrigatório)
        pon_type: tipo de PON da ONU. Valores aceitos: "gpon", "epon". (obrigatório)
        sn: número de série (SN) da ONU. (obrigatório)
        onu_type: nome do tipo/modelo da ONU (ex: "ZTE-F660V6.0"). (obrigatório)
        onu_mode: modo da ONU. Valores aceitos: "Routing", "Bridging". (obrigatório)
        zone: zona onde a ONU está localizada. Apenas alfanumérico, espaços,
            underscore e hífen. (obrigatório)
        name: nome de identificação. Apenas alfanumérico, espaços e
            @#$&()-`.+,/_ (obrigatório)
        board: placa/slot da OLT onde a ONU está. Deixe vazio se ainda não souber.
        port: porta PON da OLT onde a ONU está. Deixe vazio se ainda não souber.
        gpon_channel: canal GPON. Valores aceitos: "gpon", "xgpon", "xgspon".
        epon_channel: canal EPON. Valores aceitos: "epon", "10gepon".
        custom_profile: nome do perfil customizado (NÃO é o perfil de velocidade;
            os perfis de velocidade padrão serão usados — para trocar, use
            update_onu_speed_profiles depois de autorizar). Sem espaços no nome.
        cvlan: CVLAN-ID da ONU.
        svlan: SVLAN-ID da ONU.
        tag_transform_mode: modo de transformação de tag. Valores aceitos:
            "default", "translate", "translate-and-add".
        use_other_all_tls_vlan: usar VLAN TLS "other-all". Valores: "0" ou "1".
        vlan: VLAN-ID da ONU. Se omitido, usa a VLAN padrão da porta PON; se não
            houver VLAN padrão definida, este campo passa a ser obrigatório.
        odb: ODB/splitter. Apenas alfanumérico, espaços, underscore e hífen.
        address_or_comment: endereço ou comentário. Apenas alfanumérico, espaços
            e @#$&()-`.+,/_
        onu_external_id: ID externo único da ONU. Apenas alfanumérico.
        upload_speed_profile_name: nome do perfil de velocidade de upload.
        download_speed_profile_name: nome do perfil de velocidade de download.
    """
    data = {
        "olt_id": olt_id,
        "pon_type": pon_type,
        "gpon_channel": gpon_channel,
        "epon_channel": epon_channel,
        "board": board,
        "port": port,
        "sn": sn,
        "onu_type": onu_type,
        "custom_profile": custom_profile,
        "onu_mode": onu_mode,
        "cvlan": cvlan,
        "svlan": svlan,
        "tag_transform_mode": tag_transform_mode,
        "use_other_all_tls_vlan": use_other_all_tls_vlan,
        "vlan": vlan,
        "zone": zone,
        "odb": odb,
        "name": name,
        "address_or_comment": address_or_comment,
        "onu_external_id": onu_external_id,
        "upload_speed_profile_name": upload_speed_profile_name,
        "download_speed_profile_name": download_speed_profile_name,
    }
    return await _post("onu/authorize_onu", data=data)



@mcp.tool()
async def delete_onu(unique_external_id: str) -> dict:
    """Remove (desautoriza) uma ONU permanentemente pelo seu ID externo único.

    Ação destrutiva e normalmente irreversível pela API — a ONU some da lista de
    autorizadas e volta a aparecer como não configurada na OLT. Confirme o ID
    antes de chamar.

    Args:
        unique_external_id: ID externo único da ONU (campo "unique_external_id"
            retornado por get_all_onus_details).
    """
    return await _delete(f"onu/delete/{unique_external_id}")


@mcp.tool()
async def update_onu_sn(unique_external_id: str, sn: str, mac: str | None = None) -> dict:
    """Atualiza o número de série (SN) e/ou o MAC de uma ONU já autorizada.

    Endpoint confirmado na documentação oficial da SmartOLT: "Update ONU SN/MAC
    by ONU unique external ID" (https://api.smartolt.com/#e07cc4db-f4c9-4059-8954-f6cde6a7d422).

    Args:
        unique_external_id: ID externo único da ONU (campo "unique_external_id"
            retornado por get_all_onus_details).
        sn: novo número de série a ser gravado.
        mac: novo endereço MAC a ser gravado (opcional, quando aplicável ao modelo).
    """
    data = {"sn": sn, "mac": mac}
    return await _post(f"onu/update_sn_mac/{unique_external_id}", data=data)


@mcp.tool()
async def update_onu_vlan(onu_id: str, vlan: str) -> dict:
    """Troca a VLAN principal (main VLAN) de uma ONU já autorizada.

    Args:
        onu_id: ID da ONU a atualizar.
        vlan: novo número da VLAN a aplicar.
    """
    return await _post(f"onu/update_main_vlan/{onu_id}", data={"vlan": vlan})


@mcp.tool()
async def move_onu(onu_external_id: str, olt_id: str, board: str, port: str) -> dict:
    """Move uma ONU já autorizada para outra OLT/placa/porta PON.

    Args:
        onu_external_id: ID externo único da ONU (campo "unique_external_id"
            retornado por get_all_onus_details).
        olt_id: ID da OLT para a qual a ONU será movida. (obrigatório)
        board: placa/slot de destino — precisa existir na OLT informada. (obrigatório)
        port: porta PON de destino — precisa existir na placa informada. (obrigatório)
    """
    return await _post(
        f"onu/move/{onu_external_id}",
        data={"olt_id": olt_id, "board": board, "port": port},
    )


@mcp.tool()
async def reboot_onu(onu_id: str) -> dict:
    """Reinicia (reboot) uma ONU já autorizada.

    Args:
        onu_id: ID da ONU a reiniciar.
    """
    return await _post(f"onu/reboot/{onu_id}")


@mcp.tool()
async def resync_onu_config(onu_id: str) -> dict:
    """Reenvia (resync) a configuração salva no SmartOLT para a ONU, sem reiniciá-la.

    Útil quando a configuração da ONU dessincroniza do que está registrado no
    SmartOLT (ex: após uma queda de energia ou troca de equipamento no local).

    Args:
        onu_id: ID da ONU a re-sincronizar.
    """
    return await _post(f"onu/resync_config/{onu_id}")


@mcp.tool()
async def set_onu_wan_pppoe(onu_external_id: str, username: str, password: str) -> dict:
    """Configura a WAN de uma ONU (em modo Routing) para usar PPPoE.

    Args:
        onu_external_id: ID externo único da ONU (campo "unique_external_id"
            retornado por get_all_onus_details).
        username: usuário PPPoE. Apenas caracteres alfanuméricos, até 64 caracteres.
        password: senha PPPoE. Apenas caracteres alfanuméricos, até 64 caracteres.
    """
    return await _post(
        f"onu/set_onu_wan_mode_pppoe/{onu_external_id}",
        data={"username": username, "password": password},
    )


@mcp.tool()
async def restore_onu_factory_defaults(onu_external_id: str) -> dict:
    """Restaura uma ONU para as configurações de fábrica (factory reset).

    Ação destrutiva: apaga toda a configuração aplicada na ONU (WAN, VLAN, CATV,
    Wi-Fi, etc.), voltando-a ao estado original de fábrica. A ONU normalmente
    reinicia como parte desse processo. Confirme o ID antes de chamar — não há
    como desfazer via API.

    Args:
        onu_external_id: ID externo único da ONU (campo "unique_external_id"
            retornado por get_all_onus_details).
    """
    return await _post(f"onu/restore_factory_defaults/{onu_external_id}")


@mcp.tool()
async def get_unconfigured_onus() -> dict:
    """Lista todas as ONUs detectadas nas OLTs que ainda não foram autorizadas
    (não configuradas). Use esses dados (olt_id, board, port, sn, pon_type,
    etc.) como ponto de partida para chamar authorize_onu.
    """
    return await _get("onu/unconfigured_onus")


if __name__ == "__main__":
    import secrets
    import uvicorn

    # Streamable HTTP é o transporte recomendado hoje para conectores remotos.
    PORT = int(os.environ.get("PORT", 8000))

    MCP_SHARED_SECRET = os.environ.get("MCP_SHARED_SECRET", "")

    # A interface "Add custom connector" do Claude.ai (nesta versão) só tem um
    # campo de URL — não tem campo de headers customizados. Por isso, em vez
    # de exigir um header Authorization, colocamos o segredo como parte do
    # próprio caminho da URL: /mcp/<segredo>. Só quem tiver a URL completa
    # (com o segredo certo) consegue falar com o servidor; qualquer outro
    # caminho recebe 404 do próprio Starlette, sem revelar nada.
    STREAMABLE_PATH = f"/mcp/{MCP_SHARED_SECRET}" if MCP_SHARED_SECRET else "/mcp"

    if not MCP_SHARED_SECRET:
        print(
            "AVISO: MCP_SHARED_SECRET não definido — o servidor vai subir SEM "
            "proteção por token, em /mcp. Defina essa variável de ambiente "
            "para exigir um segredo na URL (ex: /mcp/<segredo>).",
            flush=True,
        )
    else:
        print(f"Servidor protegido — caminho MCP: {STREAMABLE_PATH}", flush=True)

    app = mcp.streamable_http_app(
        streamable_http_path=STREAMABLE_PATH,
        stateless_http=True,
        host="0.0.0.0",
    )

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")