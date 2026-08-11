"""v0.88.0-a: Domain base class + 3 domain schema 测试.

对应 12-kernel-mapping §3 Multi-Domain 抽象:
    - Domain ABC (4 abstract property: name / description / capability_ontology / profile_extensions)
    - 3 Domain: EducationDomain / ScienceDomain / CareerDomain
    - DomainRegistry singleton (register / get / list_names / has / clear / reset)

向后兼容:
    - 防御性自检 [8] 仍 hard block (Domain 不 mutate state)
    - EducationDomain 复用 v0.86.0-d DEFAULT_CAPABILITIES_LIST (Capability frozen dataclass)
"""

from __future__ import annotations

import pytest

from ecos.domain import (
    CareerDomain,
    Domain,
    DomainRegistry,
    EducationDomain,
    ScienceDomain,
    get_default_registry,
    register_default_domains,
)


# ============================================================================
# v0.88.0-a 1/16: Domain ABC 4 abstract property
# ============================================================================

def test_domain_abstract_base_class_has_4_abstract_properties():
    """Domain ABC 必须有 4 个 abstract property: name / description / capability_ontology / profile_extensions."""
    abstract_props = Domain.__abstractmethods__
    expected = {"name", "description", "capability_ontology", "profile_extensions"}
    assert expected.issubset(abstract_props), (
        f"Domain ABC 必须有 4 abstract property, got {abstract_props}"
    )


def test_domain_abstract_cannot_be_instantiated():
    """Domain ABC 不能直接 instantiate (抽象基类)."""
    with pytest.raises(TypeError):
        Domain()  # type: ignore[abstract]


# ============================================================================
# v0.88.0-a 2/16: EducationDomain 5 capability + K12 profile
# ============================================================================

def test_education_domain_name_and_description():
    """EducationDomain: name='education', description 含 K12."""
    edu = EducationDomain()
    assert edu.name == "education"
    assert "K12" in edu.description or "学科教育" in edu.description


def test_education_domain_capability_ontology_5_python():
    """EducationDomain: capability_ontology 含 5 Python default capability.

    跟 v0.86.0-d DEFAULT_CAPABILITIES_LIST 一致:
      - python_variables / python_loops / python_functions / python_conditionals / python_strings
    """
    edu = EducationDomain()
    caps = edu.list_capabilities()
    expected = {
        "python_variables", "python_loops", "python_functions",
        "python_conditionals", "python_strings",
    }
    assert set(caps) == expected, (
        f"EducationDomain capability 必须是 5 Python default, got {caps}"
    )


def test_education_domain_profile_extensions_k12():
    """EducationDomain: profile_extensions 含 grade_levels + learning_standards."""
    edu = EducationDomain()
    ext = edu.profile_extensions
    assert "grade_levels" in ext
    assert "learning_standards" in ext
    assert "elementary" in ext["grade_levels"]
    assert "middle" in ext["grade_levels"]
    assert "high" in ext["grade_levels"]


def test_education_domain_get_capability_returns_capability():
    """EducationDomain.get_capability('python_variables') 返 Capability 实例."""
    edu = EducationDomain()
    cap = edu.get_capability("python_variables")
    assert cap is not None
    assert cap.name == "python_variables"
    assert cap.domain == "python"


def test_education_domain_get_capability_missing_returns_none():
    """EducationDomain.get_capability('unknown') 返 None (防御性自检 [1])."""
    edu = EducationDomain()
    cap = edu.get_capability("nonexistent_capability")
    assert cap is None


def test_education_domain_has_capability_true_and_false():
    """EducationDomain.has_capability 正确判定."""
    edu = EducationDomain()
    assert edu.has_capability("python_variables") is True
    assert edu.has_capability("hypothesis") is False  # 别的 Domain 的 capability


def test_education_domain_to_dict():
    """EducationDomain.to_dict 序列化 4 字段."""
    edu = EducationDomain()
    d = edu.to_dict()
    assert d["name"] == "education"
    assert "description" in d
    assert "capability_ontology" in d
    assert len(d["capability_ontology"]) == 5
    assert "profile_extensions" in d


# ============================================================================
# v0.88.0-a 3/16: ScienceDomain 3 capability + research_methods
# ============================================================================

def test_science_domain_name_and_description():
    """ScienceDomain: name='science', description 含 research / 科研."""
    sci = ScienceDomain()
    assert sci.name == "science"
    assert "科研" in sci.description or "hypothesis" in sci.description


def test_science_domain_capability_ontology_3_research():
    """ScienceDomain: capability_ontology 含 3 research capability."""
    sci = ScienceDomain()
    caps = sci.list_capabilities()
    expected = {"hypothesis", "experiment", "analysis"}
    assert set(caps) == expected, (
        f"ScienceDomain capability 必须是 hypothesis / experiment / analysis, got {caps}"
    )


def test_science_domain_profile_extensions_research_methods():
    """ScienceDomain: profile_extensions 含 research_methods + domain_categories."""
    sci = ScienceDomain()
    ext = sci.profile_extensions
    assert "research_methods" in ext
    assert "empirical" in ext["research_methods"]
    assert "theoretical" in ext["research_methods"]
    assert "computational" in ext["research_methods"]
    assert "domain_categories" in ext
    assert "physics" in ext["domain_categories"]


# ============================================================================
# v0.88.0-a 4/16: CareerDomain 3 capability + vocational_tracks
# ============================================================================

def test_career_domain_name_and_description():
    """CareerDomain: name='career', description 含 职业."""
    car = CareerDomain()
    assert car.name == "career"
    assert "职业" in car.description or "skill" in car.description


def test_career_domain_capability_ontology_3_career():
    """CareerDomain: capability_ontology 含 3 career capability."""
    car = CareerDomain()
    caps = car.list_capabilities()
    expected = {"skill", "portfolio", "certification"}
    assert set(caps) == expected, (
        f"CareerDomain capability 必须是 skill / portfolio / certification, got {caps}"
    )


def test_career_domain_profile_extensions_vocational_tracks():
    """CareerDomain: profile_extensions 含 vocational_tracks + certification_levels."""
    car = CareerDomain()
    ext = car.profile_extensions
    assert "vocational_tracks" in ext
    assert "engineering" in ext["vocational_tracks"]
    assert "design" in ext["vocational_tracks"]
    assert "certification_levels" in ext
    assert "entry" in ext["certification_levels"]


# ============================================================================
# v0.88.0-a 5/16: DomainRegistry singleton + register / get / list_names / has
# ============================================================================

def test_domain_registry_singleton_pattern():
    """DomainRegistry singleton 模式: 多次构造返同一实例."""
    r1 = DomainRegistry()
    r2 = DomainRegistry()
    assert r1 is r2, "DomainRegistry 必须是 singleton"


def test_domain_registry_register_and_get():
    """DomainRegistry.register + get 往返."""
    registry = DomainRegistry()  # singleton
    registry.register(EducationDomain())
    retrieved = registry.get("education")
    assert retrieved is not None
    assert retrieved.name == "education"


def test_domain_registry_get_missing_returns_none():
    """DomainRegistry.get('unknown') 返 None (防御性自检 [1])."""
    registry = DomainRegistry()  # singleton
    result = registry.get("nonexistent_domain")
    assert result is None


def test_domain_registry_has_and_list_names():
    """DomainRegistry.has + list_names 正确反映已注册 domain."""
    registry = DomainRegistry()  # singleton
    registry.register(EducationDomain())
    registry.register(ScienceDomain())
    assert registry.has("education") is True
    assert registry.has("science") is True
    assert registry.has("career") is False  # 没注册
    names = registry.list_names()
    assert "education" in names
    assert "science" in names


def test_domain_registry_register_default_domains_helper():
    """register_default_domains() 注册 3 个 Domain (education / science / career)."""
    registry = DomainRegistry()  # singleton
    registry.clear()  # 隔离测试
    n = register_default_domains(registry=registry)
    assert n == 3
    assert registry.has("education")
    assert registry.has("science")
    assert registry.has("career")
    assert registry.get("education") is not None
    assert registry.get("science") is not None
    assert registry.get("career") is not None


def test_domain_registry_register_idempotent_overwrites():
    """DomainRegistry.register 同 name 覆盖 (idempotent)."""
    registry = DomainRegistry()  # singleton
    registry.clear()
    edu1 = EducationDomain()
    edu2 = EducationDomain()
    registry.register(edu1)
    registry.register(edu2)  # 同 name, 覆盖
    assert registry.get("education") is edu2  # 第二次的实例


def test_domain_registry_clear_isolates_test():
    """DomainRegistry.clear() 清空 registry (测试隔离)."""
    registry = DomainRegistry()  # singleton
    registry.clear()
    assert registry.list_names() == []
    registry.register(EducationDomain())
    registry.clear()
    assert registry.list_names() == []


def test_get_default_registry_returns_singleton():
    """get_default_registry() 返 DomainRegistry singleton."""
    r1 = get_default_registry()
    r2 = get_default_registry()
    assert r1 is r2
    assert isinstance(r1, DomainRegistry)


# ============================================================================
# v0.88.0-a 6/16: Domain 抽象 + capability_ontology 不可变性
# ============================================================================

def test_domain_capability_ontology_returns_copy():
    """capability_ontology 必须返 copy (防止外部修改内部状态)."""
    edu = EducationDomain()
    caps1 = edu.capability_ontology
    caps1["injected"] = "malicious"  # type: ignore[attr-defined]
    caps2 = edu.capability_ontology
    assert "injected" not in caps2, (
        "capability_ontology 必须返 copy, 外部 mutation 不应影响 Domain 内部状态"
    )


def test_domain_profile_extensions_returns_copy():
    """profile_extensions 必须返 copy (防止外部修改内部状态)."""
    edu = EducationDomain()
    ext1 = edu.profile_extensions
    ext1["injected"] = "malicious"
    ext2 = edu.profile_extensions
    assert "injected" not in ext2, (
        "profile_extensions 必须返 copy, 外部 mutation 不应影响 Domain 内部状态"
    )


def test_domain_3_instances_distinct_names():
    """3 个 Domain 实例有不同 name (key for registry)."""
    edu = EducationDomain()
    sci = ScienceDomain()
    car = CareerDomain()
    names = {edu.name, sci.name, car.name}
    assert len(names) == 3, f"3 Domain 必须有 3 不同 name, got {names}"


def test_domain_3_instances_distinct_capabilities():
    """3 个 Domain 实例有 distinct capability (没 cross-pollution)."""
    edu_caps = set(EducationDomain().list_capabilities())
    sci_caps = set(ScienceDomain().list_capabilities())
    car_caps = set(CareerDomain().list_capabilities())
    assert edu_caps.isdisjoint(sci_caps), "Education 和 Science capability 必须 disjoint"
    assert edu_caps.isdisjoint(car_caps), "Education 和 Career capability 必须 disjoint"
    assert sci_caps.isdisjoint(car_caps), "Science 和 Career capability 必须 disjoint"