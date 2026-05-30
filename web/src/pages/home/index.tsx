import { Applications } from './applications';
import { Banner } from './banner';
import { Datasets } from './datasets';

const Home = () => {
  return (
    <div className="min-h-screen bg-slate-50 px-8 py-6">
      <section className="max-w-[1600px] mx-auto">
        <Banner />
        <Datasets />
        <Applications />
      </section>
    </div>
  );
};

export default Home;
