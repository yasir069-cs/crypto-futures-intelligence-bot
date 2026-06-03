import { Router, type IRouter } from "express";
import healthRouter from "./health";
import coinsRouter from "./coins";
import marketRouter from "./market";

const router: IRouter = Router();

router.use(healthRouter);
router.use(coinsRouter);
router.use(marketRouter);

export default router;
