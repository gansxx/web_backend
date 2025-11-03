#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
递归合并指定目录下所有 *.sql 文件，输出：{时间戳}_{name}.sql
Usage:
    python merge_sql_typer.py ./sqls ./merged full_schema
"""
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer


# 当前 .py 文件所在目录的上一层
migration_dir = Path(__file__).resolve().parent.parent/"center_management/db/migration/sql_schema_migration"
output_dir=Path(__file__).resolve().parent/"migrations"

def find_sql_files(root: Path) -> list[Path]:
    """递归获取所有 .sql 文件，按文件名排序"""
    return sorted(root.rglob("*.sql"))


def merge(files: list[Path], output: Path) -> None:
    """合并文件，带简单分隔注释"""
    with output.open("w", encoding="utf-8") as out:
        out.write(f"-- Merged on {datetime.now():%F %T}\n")
        for f in files:
            out.write(f"\n-- ===== {f} =====\n")
            out.write(f.read_text(encoding="utf-8"))
            if not out.tell():
                out.write("\n")


def main(
    input_dir: Path = typer.Argument(migration_dir, help="SQL 文件所在目录"),
    output_dir: Path = typer.Argument(output_dir, help="输出目录"),
    name: str = typer.Option(...,"--name", "-n",help="自定义名字（前缀）"),
) -> None:
    if not input_dir.is_dir():
        typer.secho(f"输入目录不存在: {input_dir}", fg=typer.colors.RED)
        raise typer.Exit(1)

    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    sql_files = find_sql_files(input_dir)
    if not sql_files:
        typer.secho("未找到任何 .sql 文件", fg=typer.colors.YELLOW)
        raise typer.Exit(0)

    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    output_file = output_dir / f"{ts}_{name}.sql"

    merge(sql_files, output_file)
    typer.secho(
        f"✅ 已生成合并文件: {output_file}  （共 {len(sql_files)} 个文件）",
        fg=typer.colors.GREEN,
    )


if __name__ == "__main__":
    typer.run(main)