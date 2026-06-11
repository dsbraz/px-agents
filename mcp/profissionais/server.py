from typing import Any

from mcp.server.fastmcp import FastMCP

from brqpx_mcp.common import db
from brqpx_mcp.common.settings import settings

mcp = FastMCP(
    "profissionais",
    host=settings.mcp_host,
    port=settings.mcp_port,
)


@mcp.tool()
def people_healthcheck() -> dict[str, Any]:
    """Validate SQL Server connectivity for Portal_BAU staging."""
    return db.ping()


@mcp.tool()
def people_get_professional(num_matr_profissional: int) -> dict[str, Any] | None:
    """Return base professional data."""
    return db.fetch_one(
        """
        SELECT
            PROF.NumMatrProfissional,
            PROF.NomProfissional,
            PROF.NomEmailBRQ,
            PROF.DtaDemissao,
            PROF.IdCentroCusto,
            PROF.CodCargo,
            C.NomCargo,
            CC.NomCentroCusto,
            CC.CodStatusCentroCusto
        FROM Profissional PROF
        LEFT JOIN Cargo C ON C.CodCargo = PROF.CodCargo
        LEFT JOIN CentroCusto CC ON CC.IdCentroCusto = PROF.IdCentroCusto
        WHERE PROF.NumMatrProfissional = ?
        """,
        (num_matr_profissional,),
    )


@mcp.tool()
def people_get_professional_rate(num_matr_profissional: int) -> dict[str, Any] | None:
    """Return professional financial complement/rate data."""
    return db.fetch_one(
        """
        SELECT
            NumMatrProfissional,
            VlrRate
        FROM ComplementoFinanceiroProfissional
        WHERE NumMatrProfissional = ?
        """,
        (num_matr_profissional,),
    )


@mcp.tool()
def people_get_professional_site(num_matr_profissional: int) -> dict[str, Any] | None:
    """Return professional work location/site data."""
    return db.fetch_one(
        """
        SELECT
            COPR.NumMatrProfissional,
            COPR.IdLocalTrabalho,
            LT.CodSite,
            SI.NomExibicao
        FROM ComplementoProfissional COPR
        INNER JOIN LocalTrabalho LT ON LT.IdLocalTrabalho = COPR.IdLocalTrabalho
        INNER JOIN Site SI ON SI.CodSite = LT.CodSite
        WHERE COPR.NumMatrProfissional = ?
        """,
        (num_matr_profissional,),
    )


@mcp.tool()
def people_get_professional_cost_center(num_matr_profissional: int) -> dict[str, Any] | None:
    """Return professional cost center data."""
    return db.fetch_one(
        """
        SELECT
            PROF.NumMatrProfissional,
            PROF.IdCentroCusto,
            CC.NomCentroCusto,
            CC.CodStatusCentroCusto,
            CC.IdCentroCustoPai,
            CC.NumMatrProfissionalResponsavel
        FROM Profissional PROF
        LEFT JOIN CentroCusto CC ON CC.IdCentroCusto = PROF.IdCentroCusto
        WHERE PROF.NumMatrProfissional = ?
        """,
        (num_matr_profissional,),
    )


@mcp.tool()
def people_get_project_rh_allocations(id_projeto: int) -> list[dict[str, Any]]:
    """Return RH project allocations for a project."""
    return db.fetch_all(
        """
        SELECT
            AP.IdAlocacaoProjeto,
            AP.IdProjeto,
            AP.NumMatrProfissional,
            PROF.NomProfissional,
            PROF.NomEmailBRQ,
            AP.DtaInicioVigencia,
            AP.DtaFimVigencia,
            PROF.IdCentroCusto,
            PROF.CodCargo
        FROM AlocacaoProjeto AP
        INNER JOIN Profissional PROF
            ON PROF.NumMatrProfissional = AP.NumMatrProfissional
        WHERE AP.IdProjeto = ?
        ORDER BY AP.DtaInicioVigencia DESC, PROF.NomProfissional
        """,
        (id_projeto,),
    )


@mcp.tool()
def people_get_professionals_by_project(id_projeto: int) -> list[dict[str, Any]]:
    """Return currently active RH-allocated professionals for a project."""
    return db.fetch_all(
        """
        SELECT DISTINCT
            PROF.NumMatrProfissional,
            PROF.NomProfissional,
            PROF.NomEmailBRQ,
            PROF.DtaDemissao,
            PROF.IdCentroCusto,
            PROF.CodCargo,
            C.NomCargo,
            AP.DtaInicioVigencia,
            AP.DtaFimVigencia
        FROM Profissional PROF
        INNER JOIN AlocacaoProjeto AP
            ON AP.NumMatrProfissional = PROF.NumMatrProfissional
        LEFT JOIN Cargo C ON C.CodCargo = PROF.CodCargo
        WHERE AP.IdProjeto = ?
          AND (AP.DtaFimVigencia IS NULL OR AP.DtaFimVigencia >= CONVERT(DATE, GETDATE()))
          AND (PROF.DtaDemissao IS NULL OR PROF.DtaDemissao >= CONVERT(DATE, GETDATE()))
        ORDER BY PROF.NomProfissional
        """,
        (id_projeto,),
    )


@mcp.tool()
def people_check_professional_eligible_for_pf(
    id_projeto: int,
    id_versao: int,
    num_matr_profissional: int,
) -> dict[str, Any]:
    """Check known prerequisites for a real professional to be planned in PF."""
    professional = people_get_professional(num_matr_profissional)
    rate = people_get_professional_rate(num_matr_profissional)
    site = people_get_professional_site(num_matr_profissional)
    active_rh_allocation = db.fetch_one(
        """
        SELECT TOP 1
            IdAlocacaoProjeto,
            IdProjeto,
            NumMatrProfissional,
            DtaInicioVigencia,
            DtaFimVigencia
        FROM AlocacaoProjeto
        WHERE IdProjeto = ?
          AND NumMatrProfissional = ?
          AND (DtaFimVigencia IS NULL OR DtaFimVigencia >= CONVERT(DATE, GETDATE()))
        ORDER BY DtaInicioVigencia DESC
        """,
        (id_projeto, num_matr_profissional),
    )
    already_planned = db.fetch_one(
        """
        SELECT COUNT(1) AS Total
        FROM PlanejamentoFinanceiroAlocacao PFA
        INNER JOIN PlanejamentoFinanceiro PF
            ON PF.IdPlanejamentoFinanceiro = PFA.IdPlanejamentoFinanceiro
        WHERE PF.IdProjeto = ?
          AND PF.IdVersao = ?
          AND PFA.NumMatrProfissional = ?
        """,
        (id_projeto, id_versao, num_matr_profissional),
    )

    blockers: list[str] = []
    if professional is None:
        blockers.append("professional_not_found")
    else:
        if professional.get("DtaDemissao") is not None:
            blockers.append("professional_has_dismissal_date_check_required")
        if professional.get("CodCargo") is None:
            blockers.append("missing_cargo")
        if professional.get("CodStatusCentroCusto") not in (None, 1):
            blockers.append("cost_center_not_active")

    if active_rh_allocation is None:
        blockers.append("missing_active_rh_allocation_for_project")
    if rate is None or rate.get("VlrRate") in (None, 0):
        blockers.append("missing_financial_rate")
    if site is None:
        blockers.append("missing_work_site")
    if already_planned and already_planned.get("Total", 0) > 0:
        blockers.append("already_planned_in_pf_version")

    return {
        "eligible": not blockers,
        "blockers": blockers,
        "professional": professional,
        "rate": rate,
        "site": site,
        "active_rh_allocation": active_rh_allocation,
        "already_planned_count": already_planned.get("Total", 0) if already_planned else None,
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
