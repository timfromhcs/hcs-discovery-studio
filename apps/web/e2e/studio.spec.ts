import { test, expect, type Page } from "@playwright/test";
import { fileURLToPath } from "node:url";

const fixture = fileURLToPath(new URL("../../../tests/fixtures/e2e_library.csv", import.meta.url));

function watchForPageErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

test("workspace to import, workflow, run and results", async ({ page }) => {
  const pageErrors = watchForPageErrors(page);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Your local discovery bench" })).toBeVisible();

  await page.getByRole("button", { name: "New project" }).first().click();
  const projectDialog = page.getByRole("dialog");
  await projectDialog.locator("#project-name").fill("E2E triage");
  await projectDialog.locator("#project-description").fill("Created by the Playwright end-to-end test.");
  await projectDialog.getByRole("button", { name: "Create project" }).click();

  await expect(page).toHaveURL(/\/projects\/prj_[a-z0-9]+/);
  await expect(page.getByRole("heading", { name: "E2E triage" })).toBeVisible();

  await page.getByRole("button", { name: "Import dataset" }).first().click();
  const importDialog = page.getByRole("dialog");
  await importDialog.locator("#dataset-file").setInputFiles(fixture);
  await expect(importDialog.getByText("e2e_library.csv")).toBeVisible();
  await importDialog.getByRole("button", { name: "Import dataset" }).click();
  await expect(importDialog.getByRole("heading", { name: "Import complete" })).toBeVisible();
  await expect(importDialog.getByText("All parsed records were imported")).toBeVisible();
  await importDialog.getByRole("button", { name: "Done" }).click();

  await expect(page.getByText("e2e_library", { exact: false }).first()).toBeVisible();

  await page.locator(".sidebar").getByRole("link", { name: "Workflows" }).click();
  await expect(page.getByRole("heading", { name: "Workflows", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Use template" }).first().click();

  const nameInput = page.locator('input[aria-label="Workflow name"]');
  await expect(nameInput).toHaveValue("Basic triage");
  await expect(page.getByText("Valid · 4 execution steps")).toBeVisible();

  await page.getByRole("button", { name: "Save" }).click();
  await expect(page).toHaveURL(/\/projects\/prj_[a-z0-9]+\/workflows\/wfl_[a-z0-9]+/);

  await page.getByRole("button", { name: "Run", exact: true }).click();
  const runDialog = page.getByRole("dialog");
  await expect(runDialog.getByText("Start a reproducible run")).toBeVisible();
  await runDialog.getByRole("button", { name: "Queue run" }).click();

  await expect(page).toHaveURL(/\/runs\/run_[a-z0-9]+/);
  await expect(page.getByText("Succeeded", { exact: true }).first()).toBeVisible({ timeout: 90_000 });
  await expect(page.getByText("4 / 4")).toBeVisible();

  await page.getByRole("link", { name: "Results" }).click();
  await expect(page.getByRole("heading", { name: /Basic triage/ })).toBeVisible();
  await expect(page.locator(".scatter-svg")).toBeVisible();
  await expect(page.getByText("This run has no numeric result columns to plot.")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Column meanings" })).toBeVisible();
  await expect(page.locator(".data-table").first().locator("tbody tr")).toHaveCount(6);
  await expect(page.locator(".scatter-legend")).toContainText("Pareto front 1");
  await expect(page.getByText(/1 = non-dominated front among filter-passing records/)).toBeVisible();

  expect(pageErrors).toEqual([]);
});

test("planned engines are visible but not runnable", async ({ page }) => {
  await page.goto("/models");
  await expect(page.getByRole("heading", { name: "Engines, adapters and their real status" })).toBeVisible();
  await expect(page.getByText("AutoDock Vina")).toBeVisible();
  await expect(page.getByText("planned", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: /Run AutoDock Vina/ })).toHaveCount(0);
});

test("unknown runs fail visibly instead of fabricating a record", async ({ page }) => {
  await page.goto("/runs/run_does_not_exist");
  await expect(page.getByRole("heading", { name: "Could not load this view" })).toBeVisible();
  await expect(page.getByText(/does not exist\./)).toBeVisible();
});
