Name:           gbsteamparams
Version:        %{?_version}%{!?_version:0.1.0}
Release:        1%{?dist}
Summary:        Aplica gamemode, MangoHud e gamescope nas Launch Options da Steam
License:        MIT
URL:            https://github.com/gustavob2809/GBSteamParams
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros

Requires:       python3
Requires:       python3-pyside6
Requires:       gamemode
Requires:       mangohud

%description
Ferramenta CLI (steam-boost) e app de mesa (steam-boost-gui) para configurar
gamemode, MangoHud e gamescope automaticamente nas Launch Options de todos
os jogos da Steam, editando o localconfig.vdf do perfil local.

%prep
%autosetup -n %{name}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install

%files
%license LICENSE
%doc README.md
%{python3_sitelib}/gbsteamparams/
%{python3_sitelib}/gbsteamparams-*.dist-info/
%{_bindir}/steam-boost
%{_bindir}/steam-boost-gui

%changelog
* Sat Sep 05 2026 Gustavo <gustavob2809@gmail.com> - %{version}-1
- Build automatizado via CI
