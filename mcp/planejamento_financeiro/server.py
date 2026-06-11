from typing import Any

from mcp.server.fastmcp import FastMCP

from brqpx_mcp.common import db
from brqpx_mcp.common.settings import settings

mcp = FastMCP(
    "planejamento_financeiro",
    host=settings.mcp_host,
    port=settings.mcp_port,
)


@mcp.tool()
def pf_healthcheck() -> dict[str, Any]:
    """Validate SQL Server connectivity for Portal_BAU staging."""
    return db.ping()


@mcp.tool()
def pf_get_current_context() -> dict[str, Any] | None:
    """Return current planning competence, global lock flag, and current version."""
    return db.fetch_one(
        """
        SELECT
            C.CodCompetenciaAtual,
            C.FlgPlanejamentoBloqueado,
            V.IdVersao
        FROM Configuracao C
        LEFT JOIN Versao V ON V.CodCompetencia = C.CodCompetenciaAtual
        WHERE C.CodConfiguracao = 1
        """
    )


@mcp.tool()
def pf_check_write_allowed(id_projeto: int, id_versao: int) -> dict[str, Any]:
    """Check the minimum known gates before any future write operation."""
    row = db.fetch_one(
        """
        SELECT
            C.CodCompetenciaAtual,
            C.FlgPlanejamentoBloqueado,
            VAtual.IdVersao AS IdVersaoAtual,
            P.CodStatusProjeto,
            P.CodStatusPlanejamento,
            P.FlgProjetoDespesa
        FROM Configuracao C
        LEFT JOIN Versao VAtual ON VAtual.CodCompetencia = C.CodCompetenciaAtual
        CROSS JOIN Projeto P
        WHERE C.CodConfiguracao = 1
          AND P.IdProjeto = ?
        """,
        (id_projeto,),
    )
    if row is None:
        return {"write_allowed": False, "reasons": ["project_not_found"]}

    reasons: list[str] = []
    if row.get("FlgPlanejamentoBloqueado"):
        reasons.append("global_planning_locked")
    if row.get("IdVersaoAtual") != id_versao:
        reasons.append("historical_version_read_only")
    if row.get("CodStatusProjeto") != 1:
        reasons.append("project_not_active")

    return {"write_allowed": not reasons, "reasons": reasons, "context": row}


@mcp.tool()
def pf_get_project_planning(id_projeto: int, id_versao: int) -> dict[str, Any] | None:
    """Return the financial planning header for a project/version."""
    return db.fetch_one(
        """
        SELECT
            PF.IdPlanejamentoFinanceiro,
            PF.IdProjeto,
            PF.IdVersao,
            P.CodStatusProjeto,
            P.CodStatusPlanejamento,
            P.FlgProjetoDespesa
        FROM PlanejamentoFinanceiro PF
        INNER JOIN Projeto P ON P.IdProjeto = PF.IdProjeto
        WHERE PF.IdProjeto = ?
          AND PF.IdVersao = ?
        """,
        (id_projeto, id_versao),
    )


@mcp.tool()
def pf_get_project_competences(id_planejamento_financeiro: int) -> list[dict[str, Any]]:
    """Return monthly competences for a financial planning."""
    return db.fetch_all(
        """
        SELECT
            IdPlanejamentoFinanceiroCompetencia,
            IdPlanejamentoFinanceiro,
            CodCompetencia,
            VlrCustoPessoal,
            QtdHoraAlocacao,
            VlrCustoMedio,
            VlrCustoDireto,
            VlrFaturamento
        FROM PlanejamentoFinanceiroCompetencia
        WHERE IdPlanejamentoFinanceiro = ?
        ORDER BY CodCompetencia
        """,
        (id_planejamento_financeiro,),
    )


@mcp.tool()
def pf_get_allocations_by_project(id_projeto: int, id_versao: int) -> list[dict[str, Any]]:
    """Return PF allocation rows for professionals and TBDs in a project/version."""
    return db.fetch_all(
        """
        SELECT
            PFA.IdPlanejamentoFinanceiroAlocacao,
            PF.IdPlanejamentoFinanceiro,
            PF.IdProjeto,
            PF.IdVersao,
            PFA.NumMatrProfissional,
            PFA.CodCargo,
            PFA.CodSite,
            PFA.NomEstado,
            PFA.DscCargoPlanejamentoFinanceiroAlocacao,
            PFA.VlrRateVendido,
            PFA.FlgAplicaDissidio,
            PFA.CodTipoOferta,
            PFA.VlrRateCardVenda,
            PFA.DscCargoFuncaoCliente
        FROM PlanejamentoFinanceiroAlocacao PFA
        INNER JOIN PlanejamentoFinanceiro PF
            ON PF.IdPlanejamentoFinanceiro = PFA.IdPlanejamentoFinanceiro
        WHERE PF.IdProjeto = ?
          AND PF.IdVersao = ?
        ORDER BY PFA.NumMatrProfissional, PFA.IdPlanejamentoFinanceiroAlocacao
        """,
        (id_projeto, id_versao),
    )


@mcp.tool()
def pf_get_allocation_hours_by_month(
    id_planejamento_financeiro_alocacao: int,
) -> list[dict[str, Any]]:
    """Return planned minutes/hours and cost by competence for one allocation."""
    return db.fetch_all(
        """
        SELECT
            PFAC.IdPlanejamentoFinanceiroAlocacaoCompetencia,
            PFAC.IdPlanejamentoFinanceiroAlocacao,
            PFC.IdPlanejamentoFinanceiroCompetencia,
            PFC.CodCompetencia,
            PFAC.QtdMinutoAlocadoPlanejamentoCompetencia,
            CAST(PFAC.QtdMinutoAlocadoPlanejamentoCompetencia AS DECIMAL(18,2)) / 60.0 AS QtdHoraPlanejada,
            PFAC.VlrAlocadoCompetenciaPlanejamento,
            PFAC.VlrRate,
            PFAC.VlrRateVendido
        FROM PlanejamentoFinanceiroAlocacaoCompetencia PFAC
        INNER JOIN PlanejamentoFinanceiroCompetencia PFC
            ON PFC.IdPlanejamentoFinanceiroCompetencia = PFAC.IdPlanejamentoFinanceiroCompetencia
        WHERE PFAC.IdPlanejamentoFinanceiroAlocacao = ?
        ORDER BY PFC.CodCompetencia
        """,
        (id_planejamento_financeiro_alocacao,),
    )


@mcp.tool()
def pf_detect_overallocation(
    id_projeto: int,
    id_versao: int,
    horas_disponiveis_mes: float,
) -> list[dict[str, Any]]:
    """Detect professionals whose planned hours exceed a supplied monthly availability baseline."""
    return db.fetch_all(
        """
        SELECT
            PF.IdProjeto,
            PF.IdVersao,
            PFA.NumMatrProfissional,
            PFC.CodCompetencia,
            SUM(CAST(PFAC.QtdMinutoAlocadoPlanejamentoCompetencia AS DECIMAL(18,2)) / 60.0) AS QtdHoraPlanejada,
            ? AS QtdHoraDisponivelInformada,
            SUM(CAST(PFAC.QtdMinutoAlocadoPlanejamentoCompetencia AS DECIMAL(18,2)) / 60.0) - ? AS QtdHoraExcedente
        FROM PlanejamentoFinanceiroAlocacao PFA
        INNER JOIN PlanejamentoFinanceiro PF
            ON PF.IdPlanejamentoFinanceiro = PFA.IdPlanejamentoFinanceiro
        INNER JOIN PlanejamentoFinanceiroAlocacaoCompetencia PFAC
            ON PFAC.IdPlanejamentoFinanceiroAlocacao = PFA.IdPlanejamentoFinanceiroAlocacao
        INNER JOIN PlanejamentoFinanceiroCompetencia PFC
            ON PFC.IdPlanejamentoFinanceiroCompetencia = PFAC.IdPlanejamentoFinanceiroCompetencia
        WHERE PF.IdProjeto = ?
          AND PF.IdVersao = ?
          AND PFA.NumMatrProfissional IS NOT NULL
        GROUP BY PF.IdProjeto, PF.IdVersao, PFA.NumMatrProfissional, PFC.CodCompetencia
        HAVING SUM(CAST(PFAC.QtdMinutoAlocadoPlanejamentoCompetencia AS DECIMAL(18,2)) / 60.0) > ?
        ORDER BY PFC.CodCompetencia, PFA.NumMatrProfissional
        """,
        (
            horas_disponiveis_mes,
            horas_disponiveis_mes,
            id_projeto,
            id_versao,
            horas_disponiveis_mes,
        ),
    )


@mcp.tool()
def pf_detect_underallocation(
    id_projeto: int,
    id_versao: int,
    horas_disponiveis_mes: float,
) -> list[dict[str, Any]]:
    """Detect professionals whose planned hours are below a supplied monthly availability baseline."""
    return db.fetch_all(
        """
        SELECT
            PF.IdProjeto,
            PF.IdVersao,
            PFA.NumMatrProfissional,
            PFC.CodCompetencia,
            SUM(CAST(PFAC.QtdMinutoAlocadoPlanejamentoCompetencia AS DECIMAL(18,2)) / 60.0) AS QtdHoraPlanejada,
            ? AS QtdHoraDisponivelInformada,
            ? - SUM(CAST(PFAC.QtdMinutoAlocadoPlanejamentoCompetencia AS DECIMAL(18,2)) / 60.0) AS QtdHoraOciosaPreliminar
        FROM PlanejamentoFinanceiroAlocacao PFA
        INNER JOIN PlanejamentoFinanceiro PF
            ON PF.IdPlanejamentoFinanceiro = PFA.IdPlanejamentoFinanceiro
        INNER JOIN PlanejamentoFinanceiroAlocacaoCompetencia PFAC
            ON PFAC.IdPlanejamentoFinanceiroAlocacao = PFA.IdPlanejamentoFinanceiroAlocacao
        INNER JOIN PlanejamentoFinanceiroCompetencia PFC
            ON PFC.IdPlanejamentoFinanceiroCompetencia = PFAC.IdPlanejamentoFinanceiroCompetencia
        WHERE PF.IdProjeto = ?
          AND PF.IdVersao = ?
          AND PFA.NumMatrProfissional IS NOT NULL
        GROUP BY PF.IdProjeto, PF.IdVersao, PFA.NumMatrProfissional, PFC.CodCompetencia
        HAVING SUM(CAST(PFAC.QtdMinutoAlocadoPlanejamentoCompetencia AS DECIMAL(18,2)) / 60.0) < ?
        ORDER BY PFC.CodCompetencia, PFA.NumMatrProfissional
        """,
        (
            horas_disponiveis_mes,
            horas_disponiveis_mes,
            id_projeto,
            id_versao,
            horas_disponiveis_mes,
        ),
    )


@mcp.tool()
def pf_prepare_hours_adjustment(
    id_planejamento_financeiro_alocacao: int,
    cod_competencia: int,
    novas_horas: float,
    motivo: str,
) -> dict[str, Any]:
    """Prepare, but do not execute, a planned-hours adjustment payload."""
    current = db.fetch_one(
        """
        SELECT
            PFAC.IdPlanejamentoFinanceiroAlocacaoCompetencia,
            PFAC.IdPlanejamentoFinanceiroAlocacao,
            PFC.CodCompetencia,
            PFAC.QtdMinutoAlocadoPlanejamentoCompetencia,
            CAST(PFAC.QtdMinutoAlocadoPlanejamentoCompetencia AS DECIMAL(18,2)) / 60.0 AS QtdHoraAtual
        FROM PlanejamentoFinanceiroAlocacaoCompetencia PFAC
        INNER JOIN PlanejamentoFinanceiroCompetencia PFC
            ON PFC.IdPlanejamentoFinanceiroCompetencia = PFAC.IdPlanejamentoFinanceiroCompetencia
        WHERE PFAC.IdPlanejamentoFinanceiroAlocacao = ?
          AND PFC.CodCompetencia = ?
        """,
        (id_planejamento_financeiro_alocacao, cod_competencia),
    )
    return {
        "mode": "prepare_only",
        "will_write": False,
        "reason": "Sprint 1 MCP is read-only. Execution requires approval, recalculation rules, and audit logging.",
        "current": current,
        "proposed": {
            "id_planejamento_financeiro_alocacao": id_planejamento_financeiro_alocacao,
            "cod_competencia": cod_competencia,
            "novas_horas": novas_horas,
            "novos_minutos": int(round(novas_horas * 60)),
            "motivo": motivo,
        },
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
