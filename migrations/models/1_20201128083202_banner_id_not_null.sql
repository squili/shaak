##### upgrade #####
ALTER TABLE "banutilbanevent" ALTER COLUMN "banner_id" SET NOT NULL;
##### downgrade #####
ALTER TABLE "banutilbanevent" ALTER COLUMN "banner_id" DROP NOT NULL;
